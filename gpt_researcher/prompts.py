import warnings
from datetime import date, datetime, timezone

from .utils.enum import ReportSource, ReportType, Tone
from typing import List, Dict, Any


def generate_search_queries_prompt(
    question: str,
    parent_query: str,
    report_type: str,
    max_iterations: int = 3,
    context: List[Dict[str, Any]] = [],
):
    """Generates the search queries prompt for the given question.
    Args:
        question (str): The question to generate the search queries prompt for
        parent_query (str): The main question (only relevant for detailed reports)
        report_type (str): The report type
        max_iterations (int): The maximum number of search queries to generate
        context (str): Context for better understanding of the task with realtime web information

    Returns: str: The search queries prompt for the given question
    """

    if (
        report_type == ReportType.DetailedReport.value
        or report_type == ReportType.SubtopicReport.value
    ):
        task = f"{parent_query} - {question}"
    else:
        task = question

    context_prompt = f"""
你是一位经验丰富的研究助理，你的任务是为以下研究生成搜索查询，以找到相关的信息: "{task}".
Context: {context}

请使用Context中的信息优化你的搜索查询。该上下文提供了实时的网络信息，可以帮助你生成更加具体和相关的查询。考虑上下文中提到的任何当前事件、最新发展或特定细节，这些都可以增强您的搜索查询。
""" if context else ""

    dynamic_example = ", ".join([f'"query {i+1}"' for i in range(max_iterations)])

    return f"""编写 {max_iterations} 个谷歌搜索查询用于在线搜索，以形成关于以下任务的客观意见：“{task}”

如果需要，假设当前日期是 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}。

{context_prompt}
你的回答必须只包含一个列表，格式如下：[{dynamic_example}]。
"""


def generate_report_prompt(
    question: str,
    context,
    report_source: str,
    report_format="apa",
    total_words=1000,
    tone=None,
):
    """Generates the report prompt for the given question and research summary.
    Args: question (str): The question to generate the report prompt for
            research_summary (str): The research summary to generate the report prompt for
    Returns: str: The report prompt for the given question and research summary
    """

    reference_prompt = ""
    if report_source == ReportSource.Web.value:
        reference_prompt = f"""
你必须在报告结尾处写出所有使用的来源网址作为参考，并确保不添加重复的来源，每个来源仅列出一次。
每个网址都应该是超链接格式：[网址名称](网址)
此外，你必须在报告中提及相关网址的地方包含超链接：

例如：作者, A. A. (年, 月 日). 网页标题. 网站名称. [网址名称](网址)
"""
    else:
        reference_prompt = f"""
你必须在报告结尾处写出所有使用过的来源文档名称作为参考，并确保不添加重复的来源，每个来源仅列出一次。
"""

    tone_prompt = f"请以{tone.value} 的语气攥写报告" if tone else ""

    return f"""
信息: "{context}"
---
使用上述信息，回答以下查询或任务： "{question}" 并撰写一份详细的报告 --
报告应集中于对查询的回答，结构合理、内容丰富、深入且全面，尽可能提供事实和数据，至少{total_words}字。
您应尽量使报告尽可能长，同时使用所有相关和必要的信息。

请在报告中遵循以下所有指南：
- 您必须基于给定的信息确定自己具体且有效的意见。不要得出一般性和无意义的结论。
- 您必须以Markdown语法和{report_format}格式撰写报告。
- 您必须优先考虑所用来源的相关性、可靠性和重要性。选择可信的来源而非不太可靠的来源。
- 如果来源可信，优先选用新文章而非旧文章。
- 使用{report_format}格式中的文中引用参考，并在引用它们的句子或段落末尾放置Markdown超链接，如：([文中引用](网址))。
- 别忘了在报告结尾添加一个参考列表，采用{report_format}格式，并附上完整的网址链接（无需超链接）。
- {reference_prompt}
- {tone_prompt}

请尽最大努力，这对我的职业生涯非常重要。
假设当前日期是 {date.today()}。
"""

def curate_sources(query, sources, max_results=10):
    return f"""目标：
您的目标是评估和整理提供的爬取内容，以完成研究任务：“{query}”，并优先保留相关且高质量的信息，尤其是包含统计数据、数字或具体数据的来源。

最终整理结果将用作研究报告的背景信息，因此请优先：

- 尽量保留原始信息，特别是带有定量数据或独特见解的内容。
- 包括广泛的视角和见解。
- 仅过滤掉显然不相关或无法使用的内容。

评估指南：
1.评估每个来源时需考虑：
- 相关性：包括直接或部分与研究任务相关的来源，尽量多保留。
- 可信度：优先考虑权威来源，但除非显然不可信，否则保留其他来源。
- 时效性：优先使用最新信息，但如果旧数据重要或有价值也可保留。
- 客观性：如果有偏见的来源提供了独特或补充性视角，也应保留。
- 定量价值：优先包含带有统计数据、数字或其他具体数据的来源。

2.来源选择：
- 尽可能包括多的相关来源（最多{max_results}个），以确保广泛覆盖和多样性。
- 优先选择包含统计、数值数据或可验证事实的来源。
- 内容重复是可以接受的，尤其是数据内容的深度分析。
- 仅当来源完全不相关、严重过时或内容质量过低时，才将其排除。

3.内容保留：
- 禁止重写、总结或压缩任何来源内容。
- 保留所有可用信息，仅清理明显的垃圾或格式问题。
- 如果来源中含有有价值的数据或见解，即使只与任务部分相关或不完整，也应保留。

来源列表评估：
请在以下提供的来源列表中进行筛选：
{sources}

您必须按照原始 JSON 列表格式返回您的响应，与原始来源的 JSON 格式完全一致。
响应中不能包含任何 Markdown 格式或额外的文本（如 ```json）。请仅返回 JSON 列表！
"""




def generate_resource_report_prompt(
    question, context, report_source: str, report_format="apa", tone=None, total_words=1000
):
    """Generates the resource report prompt for the given question and research summary.

    Args:
        question (str): The question to generate the resource report prompt for.
        context (str): The research summary to generate the resource report prompt for.

    Returns:
        str: The resource report prompt for the given question and research summary.
    """

    reference_prompt = ""
    if report_source == ReportSource.Web.value:
        reference_prompt = f"""
            你必须包含所有相关来源的网址。 每个网址应使用超链接格式：[网址名称](网址)。
            """
    else:
        reference_prompt = f"""
            你必须在报告末尾列出所有使用过的来源文档名称作为参考，并确保不要添加重复的来源，每个来源仅列出一次。 "
        """

    return (
        f'"""{context}"""\n\n基于上述信息，为以下问题或主题生成一份参考资料推荐报告："{question}"。 ' 
        "报告应提供每个推荐资源的详细分析，解释每个来源如何帮助回答研究问题。  "
        "重点关注每个来源的相关性、可靠性和重要性。"
        "确保报告结构清晰、内容翔实且深入，并遵循 Markdown 语法。"
        "尽可能包括相关事实、数据和数字。"
        f"报告的最小长度应为 {total_words} 字。"
        "你必须包含所有相关来源的网址。"
        "每个网址应使用超链接格式：[网址名称](网址)。"
        f'{reference_prompt}'
    )


def generate_custom_report_prompt(
    query_prompt, context, report_source: str, report_format="apa", tone=None, total_words=1000
):
    return f'"{context}"\n\n{query_prompt}'


def generate_outline_report_prompt(
    question, context, report_source: str, report_format="apa", tone=None,  total_words=1000
):
    """Generates the outline report prompt for the given question and research summary.
    Args: question (str): The question to generate the outline report prompt for
            research_summary (str): The research summary to generate the outline report prompt for
    Returns: str: The outline report prompt for the given question and research summary
    """

    return (
        f'"""{context}""" 使用以上信息，为以下问题或主题生成一份研究报告的大纲（采用Markdown语法）'
        f' : "{question}". 该大纲应提供一份结构良好的框架，包括研究报告的主要章节、子章节，以及需要涵盖的关键点。'
        f" 研究报告应详细、信息丰富、深入，并且至少包含 {total_words} 个单词。使用适当的Markdown语法来格式化大纲，并确保其可读性。"
    )


def get_report_by_type(report_type: str):
    report_type_mapping = {
        ReportType.ResearchReport.value: generate_report_prompt,
        ReportType.ResourceReport.value: generate_resource_report_prompt,
        ReportType.OutlineReport.value: generate_outline_report_prompt,
        ReportType.CustomReport.value: generate_custom_report_prompt,
        ReportType.SubtopicReport.value: generate_subtopic_report_prompt,
    }
    return report_type_mapping[report_type]


def auto_agent_instructions():
    return """
这个任务涉及对给定主题进行研究，无论其复杂性或是否存在明确答案。研究由特定类型和角色的服务完成，每种服务需要不同的指令。
代理（Agent）
服务的选择基于主题领域和可以用来研究该主题的具体服务名称。代理根据其专业领域分类，每种服务类型都与一个对应的表情符号相关联。

示例：
任务: “我应该投资苹果股票吗？”
响应: 
{
    "server": "💰 财务代理",
    "agent_role_prompt": "你是一名经验丰富的财务分析AI助手。你的主要目标是基于提供的数据和趋势，撰写全面、深刻、公正且方法论严谨的财务报告。"
}
任务: “倒卖运动鞋会变得有利可图吗？”
响应: 
{ 
    "server":  "📈 商业分析代理",
    "agent_role_prompt": "你是一名经验丰富的AI商业分析助手。你的主要目标是基于提供的商业数据、市场趋势和战略分析，生成全面、深刻、公正且系统化的商业报告。"
}
任务: “特拉维夫有哪些最有趣的景点？”
响应:
{
    "server":  "🌍 旅行代理",
    "agent_role_prompt": "你是一名见多识广的AI旅行助手。你的主要目的是针对给定地点撰写有趣、深刻、公正且结构良好的旅行报告，包括历史、景点和文化见解。"
}
"""


def generate_summary_prompt(query, data):
    """Generates the summary prompt for the given question and text.
    Args: question (str): The question to generate the summary prompt for
            text (str): The text to generate the summary prompt for
    Returns: str: The summary prompt for the given question and text
    """

    return (
        f'{data}\n 使用上述文本，基于以下任务或查询总结内容：“{query}”。如果无法使用文本回答查询，你必须对文本进行简要总结。包括所有可用的事实性信息，例如数字、统计数据、引言等。'
    )


################################################################################################

# DETAILED REPORT PROMPTS


def generate_subtopics_prompt() -> str:
    return """
在提供的主要主题：

{task}

和研究数据：

{data}

的基础上：

构建一个子主题列表，这些子主题将作为任务报告文档的标题。
以下是可能的子主题列表：{subtopics}。
子主题之间不能有重复内容。
子主题数量限制为最多 {max_subtopics} 个。
最后按照任务的相关性和意义对子主题进行排序，使其呈现为详细报告中合理且可展示的顺序。
“重要！”

每个子主题必须仅与主要主题和提供的研究数据相关！
{format_instructions}
"""


def generate_subtopic_report_prompt(
    current_subtopic,
    existing_headers: list,
    relevant_written_contents: list,
    main_topic: str,
    context,
    report_format: str = "apa",
    max_subsections=5,
    total_words=800,
    tone: Tone = Tone.Objective,
) -> str:
    return f"""
上下文：
"{context}"

主要主题和子主题：
基于最新可用信息，围绕主主题：{main_topic} 下的子主题：{current_subtopic}，构建一个详细报告。  
子章节的数量必须限制在最多 {max_subsections} 个。

内容重点：
- 报告应专注于回答问题，结构良好、信息丰富、深入且包含事实和数字（如有）。  
- 使用 Markdown 语法并遵循 {report_format.upper()} 格式。

重要说明：内容和章节的独特性：
- 确保内容独特且不与现有报告重复是至关重要的一部分。  
- 在撰写任何新子章节之前，请仔细检查以下提供的现有标题和已有内容。  
- 防止新内容与现有内容重复或有过于相似的变体，以避免重复。  
- 新的子章节标题不得使用现有标题。  
- 避免重复现有内容或已有子主题报告的相关变体。  
- 如果添加嵌套子章节，确保它们的内容独特，且未包含在现有子主题报告中。  
- 确保内容完全新颖且不与之前的子主题报告的任何信息重叠。

"现有子主题报告":
- 现有子主题报告及其章节标题：

    {existing_headers}

- 来自之前子主题报告的现有内容：

    {relevant_written_contents}

"结构和格式要求":
- 由于此子报告将作为更大报告的一部分，请仅包括主体内容，分为适当的子主题部分，不需要任何引言或结论部分。  

- 必须使用 Markdown 超链接将报告中引用的相关来源 URL 关联，例如：

    ### 部分标题

    这是示例文本。([url 网站](url))

- 使用 H2 标题（##）作为主要子主题标题，H3 标题（###）作为子章节标题。  
- 使用较小的 Markdown 标题（例如 H2 或 H3）进行内容结构化，避免使用最大的标题（H1），因为它将用于整个报告的标题。  
- 将内容组织成独立的章节，使其补充但不与现有报告重复。  
- 当向报告添加类似或相同的子章节时，必须明确指出新内容与现有内容之间的区别。例如：

    ### 新标题（与现有标题类似）

    虽然上一部分讨论了[主题 A]，但本节将探讨[主题 B]。

"日期":
如有必要，请假设当前日期为 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}。

"重要提示！":
- 内容必须聚焦于主要主题！必须排除任何无关信息！  
- 不得添加任何引言、结论、摘要或参考文献部分。  
- 必须使用 Markdown 语法超链接 ([url 网站](url)) 到相关句子中的必要位置。  
- 如果添加了类似或相同的子章节，必须在报告中明确提及新内容与现有内容之间的区别。  
- 报告的最小字数必须为 {total_words}。  
- 整个报告应保持 {tone.value} 的语气。

不得添加结论部分。
"""


def generate_draft_titles_prompt(
    current_subtopic: str,
    main_topic: str,
    context: str,
    max_subsections: int = 5
) -> str:
    return f"""

基于最新的可用信息，围绕主主题：{main_topic} 下的子主题：{current_subtopic}，构建一份详细报告的草稿章节标题。

"任务"：
1. 创建子主题报告的草稿章节标题列表。
2. 每个标题应简洁且与子主题相关。
3. 标题不应过于笼统，而是足够详细地涵盖子主题的主要方面。
4. 使用 Markdown 语法书写标题，使用 H3 (###)，因为 H1 和 H2 将用于更大报告的标题。
5. 确保标题涵盖子主题的主要方面。

"结构与格式要求"：
以列表格式提供草稿标题，使用 Markdown 语法，例如：

### 标题 1  
### 标题 2  
### 标题 3  

"重要提示！"：
- 必须聚焦于主要主题！必须排除任何无关信息！  
- 不得添加任何引言、结论、摘要或参考文献部分。  
- 专注于创建标题，而不是内容。
"""


def generate_report_introduction(question: str, research_summary: str = "") -> str:
    return f"""{research_summary}\n 
基于以上最新信息，准备一个关于主题“{question}”的详细报告引言。
- 引言应简洁、结构良好、信息丰富，并使用 Markdown 语法。
- 由于该引言将成为更大报告的一部分，请勿包含报告中通常存在的其他部分。
- 引言前应以 H1 标题呈现，并提供适合整份报告的主题标题。
- 必须在必要时为句子添加相关的 Markdown 格式超链接（[url website](url)）。
如有需要，假定当前日期为 {datetime.now(timezone.utc).strftime('%Y-%m-%d')}。
"""


def generate_report_conclusion(query: str, report_content: str) -> str:
    """
    Generate a concise conclusion summarizing the main findings and implications of a research report.

    Args:
        report_content (str): The content of the research report.

    Returns:
        str: A concise conclusion summarizing the report's main findings and implications.
    """
    prompt = f"""
    根据以下研究报告和研究任务，请撰写一份简明的结论，总结主要发现及其影响：

    研究任务：{query}
    
    研究报告：{report_content}
    
    您的结论应包含：
    
    1.概括研究的主要要点
    2.突出最重要的发现
    3.讨论任何相关影响或后续步骤
    4.长度为大约 2-3 段
    5.如果报告末尾没有标注“## 结论”作为结论部分标题，请在您的结论顶部添加该标题。
    6.您必须在必要时为句子添加相关的 Markdown 格式超链接([url website](url))。
    
    撰写结论：
    """

    return prompt


report_type_mapping = {
    ReportType.ResearchReport.value: generate_report_prompt,
    ReportType.ResourceReport.value: generate_resource_report_prompt,
    ReportType.OutlineReport.value: generate_outline_report_prompt,
    ReportType.CustomReport.value: generate_custom_report_prompt,
    ReportType.SubtopicReport.value: generate_subtopic_report_prompt,
}


def get_prompt_by_report_type(report_type):
    prompt_by_type = report_type_mapping.get(report_type)
    default_report_type = ReportType.ResearchReport.value
    if not prompt_by_type:
        warnings.warn(
            f"Invalid report type: {report_type}.\n"
            f"Please use one of the following: {', '.join([enum_value for enum_value in report_type_mapping.keys()])}\n"
            f"Using default report type: {default_report_type} prompt.",
            UserWarning,
        )
        prompt_by_type = report_type_mapping.get(default_report_type)
    return prompt_by_type

