import gradio as gr
from openai import OpenAI
from bs4 import BeautifulSoup
from urllib.parse import quote
from readability import Document
import requests

# 获取网页内容

# 初始化 API 客户端
client = OpenAI(
    api_key="*****",
    base_url="*****"
)

# 用于记录多轮对话的全局会话历史（API 格式）
conversation_history = [
    {"role": "system", "content": "你是辅助机器人。你来和我进行对话。"}
]
saved_history=[]

def search_with_bing(query, retry=2):
    url = f'https://cn.bing.com/search?q={quote(query)}&qs=n&form=QBRE&sp=-1&lq=0'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    resp = requests.get(url, headers=headers, timeout=5)

    soup = BeautifulSoup(resp.text, 'html.parser')

    results = soup.find_all('li', class_='b_algo')
    # 遍历搜索结果，提取标题和链接
    search_results = []
    for result in results:
        title = result.find('h2').text  # 提取标题文字
        link = result.find('a')['href']  # 提取链接
        print('标题:', title)
        print('链接:', link)
        print('---')
        search_results.append({"title": title, "link": link})
    if not search_results and retry > 0:
        search_results = search_with_bing(query, retry - 1)
        return search_results
    return search_results


def format_search_results(results: list, max_results: int = 2) -> str:
    """
    Format the top search results into a context string.
    """
    formatted = []
    success=0
    iter=0
    while success < max_results and len(results) > iter:
        result = results[iter]
        iter+=1
        title = result.get("title", "No title")
        url = result.get("link", "")
        try:
            response = requests.get(url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                })  # 限制超时时间，避免卡死
            response.encoding = 'utf-8'
            if response.status_code == 200:
                success+=1
                html_content = response.text
                # 使用BeautifulSoup提取标题
                # 使用Readability提取主要内容
                doc = Document(html_content)



                content = doc.summary()  # 获取主要内容
                # 获取文章标题
                print(f"标题: {title}")
                print("正文:")
                print(content, "\n"*4)
                formatted.append(
                    f"Title: {title}\nURL: {url}\n" + "content:" + (
                        (content[:1000] + "...") if len(content) > 1000 else content))

            else:
                print(f"Failed to fetch URL {url}, status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
    print("\n\n".join(formatted))
    return "\n\n".join(formatted)


def chat_with_model(user_input, chat_history, internet, max_history=19):
    global conversation_history,saved_history
    chat_history = saved_history
    if len(conversation_history) > max_history:
        conversation_history = conversation_history[0:1] + conversation_history[-max_history + 1:]
    # 如果用户输入以 "search:" 开头，则触发联网搜索
    query = user_input
    if internet:
        results = search_with_bing(query)
        print("Search results:", results)
        if results:
            search_result = format_search_results(results, max_results=2)
            # 将搜索结果以系统消息的形式加入会话历史
            composite_prompt = """请使用下方在网络中搜索到的相关信息（<<<context>>><<</context>>>之间的部分）回答我的问题，如果所提供的在网络中搜索到的相关信息足以回答问题（或为空），请根据自己的理解回答这个问题。
            如果使用了网络搜索的信息，一定要在回答过程中如果需要说明引用了哪一个网络链接的内容，给该信息的出链接地址和标题，用论文引用格式上标书写。”  
            <<<context>>>  
            {context}  
            <<</context>>>  

            用户提问：{query}  
            请回答：  
            """.format(query=query, context=search_result)
            # 将用户输入加入会话历史
            conversation_history.append({"role": "user", "content": composite_prompt})
        conversation_history.append({"role": "user", "content": user_input})
    else:
        conversation_history.append({"role": "user", "content": user_input})

    # 调用 API，开启流式传输
    stream_response = client.chat.completions.create(
        model="deepseek-r1",
        messages=conversation_history,
        stream=True  # 启用流式传输
    )
    if stream_response.response.status_code == 403:
        conversation_history.append({"role": "assistant", "content": "对不起，tokens数量超出限制，请清除历史记录。请重新尝试。"})
    else:
        response_text = ""
        reason_text = ""
        # 利用 yield 逐步返回生成的部分答案，实现流式展示
        for chunk in stream_response:
            # 注意：这里假设返回的数据格式与 OpenAI API 类似
            delta = chunk.choices[0].delta

            if delta:
                if delta.content:
                    response_text += delta.content
                elif delta.reasoning_content:
                    reason_text += delta.reasoning_content

            res = ""
            if reason_text:
                res += "### 推理过程:\n<small>" + reason_text + "\n</small>"
            if response_text:
                res += "\n***\n"
                res += "# deepseek回答:\n" + response_text

            updated_history = chat_history + [(user_input, res)]
            yield updated_history

        # 流式结束后，将完整的回复加入会话历史，保证多轮对话的连续性
        conversation_history.append({"role": "assistant", "content": response_text})
        saved_history = chat_history + [(user_input, res)]
        yield chat_history + [(user_input, res)]

def clear_history():
    global conversation_history,saved_history
    conversation_history = [
        {"role": "system", "content": "你是辅助机器人。你来和我进行对话。"}
    ]
    saved_history=[]

# 构建 Gradio 界面
with gr.Blocks() as demo:
    gr.HTML(
        '<a style="background-color: #0077b6; color: #fff; padding: 10px; border-radius: 5px; text-decoration: none;"'
        ' href="https://www.dovahwall.cn" target="_blank"><button>Go to Dovahwall.cn</button></a>')
    gr.HTML(
        '<a style="background-color: #0077b6; color: #fff; padding: 10px; border-radius: 5px; text-decoration: none;"'
        ' href="http://www.dovahwall.cn:8033" target="_blank"><button>chat with gpt</button></a>')
    gr.Markdown("## Chat with Deepseek\n- 输入普通文本进行对话\n")
    chatbot = gr.Chatbot()
    with gr.Row():
        txt = gr.Textbox(show_label=False, placeholder="请输入消息")

    with gr.Row():
        btn = gr.Button("发送")
        internet = gr.Checkbox(label="联网搜索")
        clear = gr.Button("清空历史")

    txt.submit(chat_with_model, inputs=[txt, chatbot, internet], outputs=[chatbot])
    btn.click(chat_with_model, inputs=[txt, chatbot, internet], outputs=[chatbot])
    clear.click(clear_history, outputs=[chatbot])
demo.launch(server_name="0.0.0.0", server_port=8034)