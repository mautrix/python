# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest

from . import parse_html


async def test_basic_markdown() -> None:
    tests = {
        "<b>test</b>": "**test**",
        "<strong>t<em>e<del>s</del>t</em>!</strong>": "**t_e~~s~~t_!**",
        "<a href='https://example.com'>example</a>": "[example](https://example.com)",
        "<pre><code class='language-css'>div {\n    display: none;\n}</code></pre>": "```css\ndiv {\n    display: none;\n}\n```",
        "<code>hello</code>": "`hello`",
        "<blockquote>Testing<br>123</blockquote>": "> Testing\n> 123",
        "<ul><li>test</li>\n<li>foo</li>\n<li>bar</li>\n</ul>": "● test\n● foo\n● bar",
        "<ol start=123><li>test</li>\n<li>foo</li>\n<li>bar</li>\n</ol>": "123. test\n124. foo\n125. bar",
        "<h4>header</h4>": "#### header",
        "<span data-mx-spoiler>spoiler?</span>": "||spoiler?||",
        "<span data-mx-spoiler='SPOILER!'>not really</span>": "||SPOILER!|not really||",
    }
    for html, markdown_ish in tests.items():
        assert await parse_html(html) == markdown_ish


async def test_nested_markdown() -> None:
    input_html = """
<h1>Hello, World!</h1>
<blockquote>
  <ol>
    <li><a href='https://example.com'>example</a></li>
    <li>
      <ul>
        <li>item 1</li>
        <li>item 2</li>
      </ul>
    </li>
    <li>
      <pre><code class="language-python">def random() -> int:
    if 4 is 1:
        return 5
    return 4</code></pre>
    </li>
    <li><strong>Just some text</strong></li>
  </ol>
</blockquote>
""".strip()
    expected_output = """
# Hello, World!
> 1. [example](https://example.com)
> 2. ● item 1
>    ● item 2
> 3. ```python
>    def random() -> int:
>        if 4 is 1:
>            return 5
>        return 4
>    ```
> 4. **Just some text**
""".strip()
    assert await parse_html(input_html) == expected_output
