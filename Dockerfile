FROM python:3.10.13
MAINTAINER dovahlore

 # 设置 python 环境变量
ENV PYTHONUNBUFFERED 1
# 容器内创建项目目录
RUN mkdir -p /ai
WORKDIR /ai
# 将当前目录下文件 放入容器指定目录
ADD . /ai
# 更新pip
RUN /usr/local/bin/python -m pip install --upgrade pip

# 安装依赖
RUN pip3 install -r requirements.txt


# 暴露容器内的端口

EXPOSE 8033 8034

CMD python seek.py & python gpt.py & wait
LABEL name=ai