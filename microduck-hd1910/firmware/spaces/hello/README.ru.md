---
title: hello duck
emoji: 🦆
colorFrom: yellow
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Smallest Docker Space that has a WebSocket route and Gradio.
---
[Оригинал](README.md) | **Русский**

# hello duck

Намеренно минимальный Docker Space, опубликованный, чтобы определить, что из четырёх составляющих ломает основной: контейнер, собственный маршрут WebSocket, Gradio под FastAPI или Hugging Face OAuth.

Здесь есть первые три, но **нет** OAuth, где произошёл последний сбой. Возвращайте части по одной вместо одновременной отладки всех четырёх.
