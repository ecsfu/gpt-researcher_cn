import asyncio
import random
import json
from typing import Dict, Optional

from ..actions.utils import stream_output
from ..actions.query_processing import plan_research_outline, get_search_results
from ..document import DocumentLoader, LangChainDocumentLoader
from ..utils.enum import ReportSource, ReportType, Tone


class ResearchConductor:
    """Manages and coordinates the research process."""

    def __init__(self, researcher):
        self.researcher = researcher

    async def plan_research(self, query): #搜索网络
        await stream_output(
            "logs",
            "planning_research",
            f"🌐 为以下问题进行网络搜索: {query}...",
            self.researcher.websocket,
        )

        search_results = await get_search_results(query, self.researcher.retrievers[0])

        await stream_output(
            "logs",
            "planning_research",
            f"🤔 开始生成研究策略和子问题 (可能会花费几分钟的时间)...",
            self.researcher.websocket,
        )

        return await plan_research_outline(  #返回子问题
            query=query,
            search_results=search_results,
            agent_role_prompt=self.researcher.role,
            cfg=self.researcher.cfg,
            parent_query=self.researcher.parent_query,
            report_type=self.researcher.report_type,
            cost_callback=self.researcher.add_costs,
        )

    async def conduct_research(self):
        """
        Runs the GPT Researcher to conduct research
        """
        # Reset visited_urls and source_urls at the start of each research task
        self.researcher.visited_urls.clear()
        research_data = []

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "starting_research",
                f"🔍 开始研究任务： '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        if self.researcher.verbose:
            await stream_output("logs", "agent_generated", self.researcher.agent, self.researcher.websocket)

        # Research for relevant sources based on source types below
        if self.researcher.source_urls:
            # If specified, the researcher will use the given urls as the context for the research.
            research_data = await self._get_context_by_urls(self.researcher.source_urls)
            if research_data and len(research_data) == 0 and self.verbose:
                # Could not find any relevant resources in source_urls to answer the query or sub-query. Will answer using model's inherent knowledge
                await stream_output(
                    "logs",
                    "answering_from_memory",
                    f"🧐 无法从提供的数据源中找到相关信息...",
                    self.websocket,
                )
            # If complement_source_urls parameter is set, more resources can be gathered to create additional context using default web search
            if self.researcher.complement_source_urls:
                additional_research = await self._get_context_by_web_search(self.researcher.query)
                research_data += ' '.join(additional_research)

        elif self.researcher.report_source == ReportSource.Local.value:
            document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()
            if self.researcher.vector_store:
                self.researcher.vector_store.load(document_data)

            research_data = await self._get_context_by_web_search(self.researcher.query, document_data)

        # Hybrid search including both local documents and web sources
        elif self.researcher.report_source == ReportSource.Hybrid.value:
            document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()
            if self.researcher.vector_store:
                self.researcher.vector_store.load(document_data)
            docs_context = await self._get_context_by_web_search(self.researcher.query, document_data)
            web_context = await self._get_context_by_web_search(self.researcher.query)
            research_data = f"来自本地文档中的内容: {docs_context}\n\n来自网页的内容: {web_context}"

        elif self.researcher.report_source == ReportSource.LangChainDocuments.value:
            langchain_documents_data = await LangChainDocumentLoader(
                self.researcher.documents
            ).load()
            if self.researcher.vector_store:
                self.researcher.vector_store.load(langchain_documents_data)
            research_data = await self._get_context_by_web_search(
                self.researcher.query, langchain_documents_data
            )

        elif self.researcher.report_source == ReportSource.LangChainVectorStore.value:
            research_data = await self._get_context_by_vectorstore(self.researcher.query, self.researcher.vector_store_filter)
        # Default web based research
        elif self.researcher.report_source == ReportSource.Web.value:
            research_data = await self._get_context_by_web_search(self.researcher.query)

        # Rank and curate the sources based on the research data
        self.researcher.context = research_data
        if self.researcher.cfg.curate_sources:
            self.researcher.context = await self.researcher.source_curator.curate_sources(research_data)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "research_step_finalized",
                f"Finalized research step.\n💸 Total Research Costs: ${self.researcher.get_costs()}",
                self.researcher.websocket,
            )

        return self.researcher.context

    async def _get_context_by_urls(self, urls):
        """
        Scrapes and compresses the context from the given urls
        """
        new_search_urls = await self._get_new_urls(urls)
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "source_urls",
                f"🗂️ 开始从以下链接获取信息: {new_search_urls}...",
                self.researcher.websocket,
            )

        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)

        if self.researcher.vector_store:
            self.researcher.vector_store.load(scraped_content)

        return await self.researcher.context_manager.get_similar_content_by_query(self.researcher.query, scraped_content)

    async def _get_context_by_vectorstore(self, query, filter: Optional[dict] = None):
        """
        Generates the context for the research task by searching the vectorstore
        Returns:
            context: List of context
        """
        context = []
        # Generate Sub-Queries including original query
        sub_queries = await self.plan_research(query)
        # If this is not part of a sub researcher, add original query to research for better results
        if self.researcher.report_type != "subtopic_report":
            sub_queries.append(query)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️  I will conduct my research based on the following queries: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        # Using asyncio.gather to process the sub_queries asynchronously
        context = await asyncio.gather(
            *[
                self._process_sub_query_with_vectorstore(sub_query, filter)
                for sub_query in sub_queries
            ]
        )
        return context

    async def _get_context_by_web_search(self, query, scraped_data: list = []):
        """
        Generates the context for the research task by searching the query and scraping the results
        Returns:
            context: List of context
        """
        # Generate Sub-Queries including original query
        sub_queries = await self.plan_research(query)
        # If this is not part of a sub researcher, add original query to research for better results
        if self.researcher.report_type != "subtopic_report":
            sub_queries.append(query)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️ 我将基于下面的子问题开展研究: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        # Using asyncio.gather to process the sub_queries asynchronously
        context = await asyncio.gather(
            *[
                self._process_sub_query(sub_query, scraped_data)
                for sub_query in sub_queries
            ]
        )
        return context

    async def _process_sub_query(self, sub_query: str, scraped_data: list = []):
        """Takes in a sub query and scrapes urls based on it and gathers context.

        Args:
            sub_query (str): The sub-query generated from the original query
            scraped_data (list): Scraped data passed in

        Returns:
            str: The context gathered from search
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "running_subquery_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        if not scraped_data:
            scraped_data = await self._scrape_data_by_urls(sub_query)

        content = await self.researcher.context_manager.get_similar_content_by_query(sub_query, scraped_data)

        if content and self.researcher.verbose:
            await stream_output(
                "logs", "subquery_context_window", f"📃 {content}", self.researcher.websocket
            )
        elif self.researcher.verbose:
            await stream_output(
                "logs",
                "subquery_context_not_found",
                f"🤷 No content found for '{sub_query}'...",
                self.researcher.websocket,
            )
        return content

    async def _process_sub_query_with_vectorstore(self, sub_query: str, filter: Optional[dict] = None):
        """Takes in a sub query and gathers context from the user provided vector store

        Args:
            sub_query (str): The sub-query generated from the original query

        Returns:
            str: The context gathered from search
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "running_subquery_with_vectorstore_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        content = await self.researcher.context_manager.get_similar_content_by_query_with_vectorstore(sub_query, filter)

        if content and self.researcher.verbose:
            await stream_output(
                "logs", "subquery_context_window", f"📃 {content}", self.researcher.websocket
            )
        elif self.researcher.verbose:
            await stream_output(
                "logs",
                "subquery_context_not_found",
                f"🤷 No content found for '{sub_query}'...",
                self.researcher.websocket,
            )
        return content

    async def _get_new_urls(self, url_set_input):
        """Gets the new urls from the given url set.
        Args: url_set_input (set[str]): The url set to get the new urls from
        Returns: list[str]: The new urls from the given url set
        """

        new_urls = []
        for url in url_set_input:
            if url not in self.researcher.visited_urls:
                self.researcher.visited_urls.add(url)
                new_urls.append(url)
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "added_source_url",
                        f"✅ 加入以下研究链接: {url}\n",
                        self.researcher.websocket,
                        True,
                        url,
                    )

        return new_urls

    async def _search_relevant_source_urls(self, query):
        new_search_urls = []

        # Iterate through all retrievers
        for retriever_class in self.researcher.retrievers:
            # Instantiate the retriever with the sub-query
            retriever = retriever_class(query)

            # Perform the search using the current retriever
            search_results = await asyncio.to_thread(
                retriever.search, max_results=self.researcher.cfg.max_search_results_per_query
            )

            # Collect new URLs from search results
            search_urls = [url.get("href") for url in search_results]
            new_search_urls.extend(search_urls)

        # Get unique URLs
        new_search_urls = await self._get_new_urls(new_search_urls)
        random.shuffle(new_search_urls)

        return new_search_urls

    async def _scrape_data_by_urls(self, sub_query):
        """
        Runs a sub-query across multiple retrievers and scrapes the resulting URLs.

        Args:
            sub_query (str): The sub-query to search for.

        Returns:
            list: A list of scraped content results.
        """
        new_search_urls = await self._search_relevant_source_urls(sub_query)

        # Log the research process if verbose mode is on
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "researching",
                f"🤔 Researching for relevant information across multiple sources...\n",
                self.researcher.websocket,
            )

        # Scrape the new URLs
        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)

        if self.researcher.vector_store:
            self.researcher.vector_store.load(scraped_content)

        return scraped_content
