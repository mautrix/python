from lxml import html

HTMLNode = html.HtmlElement


def read_html(data: str) -> HTMLNode:
    return html.fromstring(data)
