#!/usr/bin/env python3
"""Публикация статьи на cephfix.com (RU + EN).

Запуск из корня репозитория сайта:
    python3 _templates/publish.py article.json            # новая статья
    python3 _templates/publish.py article.json --update   # заменить уже опубликованную

article.json:
{
  "slug": "steiner-analysis",              # латиница, цифры, дефисы
  "date": "2026-11-09",                    # необязательно, по умолчанию сегодня
  "ru": {"title": "...", "description": "...", "body": "ru.html"},
  "en": {"title": "...", "description": "...", "body": "en.html"}
}
"body" — путь к HTML-фрагменту тела статьи (без <h1>: заголовок подставляет шаблон).
Разрешены теги: h2 h3 h4 p ul ol li table thead tbody tr th td strong em b i a
blockquote code sup sub br hr abbr. Без скриптов, стилей, картинок и атрибутов on*.

Скрипт создаёт articles/<slug>/index.html и en/articles/<slug>/index.html,
добавляет статью в оба списка статей, в sitemap.xml и (один раз) ссылку
«Статьи» в меню главной страницы. Других файлов не трогает.
"""
import datetime as dt
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path.cwd()
TPL = ROOT / '_templates'
SITE = 'https://cephfix.com'

ALLOWED = {
    'h2': set(), 'h3': set(), 'h4': set(), 'p': set(), 'ul': set(), 'ol': {'start'},
    'li': set(), 'table': set(), 'thead': set(), 'tbody': set(), 'tr': set(),
    'th': {'colspan', 'rowspan', 'scope'}, 'td': {'colspan', 'rowspan'},
    'strong': set(), 'em': set(), 'b': set(), 'i': set(), 'a': {'href', 'title'},
    'blockquote': set(), 'code': set(), 'sup': set(), 'sub': set(), 'br': set(),
    'hr': set(), 'abbr': {'title'}, 'div': {'class'},
}
VOID = {'br', 'hr'}
HREF_OK = re.compile(r'^(https?://|/|#|mailto:)', re.I)
MONTHS_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
             'августа', 'сентября', 'октября', 'ноября', 'декабря']

NAV_LINK = '<a href="/articles/" data-href-en="/en/articles/" data-i18n="nav_art">Статьи</a>'
MARKERS = {'<!--NAV-ARTICLES-->': NAV_LINK, '<!--FOOT-ARTICLES-->': NAV_LINK}


def fail(msg):
    print('ОШИБКА:', msg)
    sys.exit(1)


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.words = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            self.errors.append(f'тег <{tag}> не разрешён')
            return
        for k, v in attrs:
            if k not in ALLOWED[tag]:
                self.errors.append(f'атрибут {k} у <{tag}> не разрешён')
            if k == 'href' and not HREF_OK.match(v or ''):
                self.errors.append(f'недопустимая ссылка: {v}')
            if k == 'class' and v != 'tbl':
                self.errors.append(f'класс {v} не разрешён')
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f'незакрытый или лишний </{tag}> (открыто: {self.stack[-3:]})')
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()

    def handle_data(self, data):
        self.words += len(data.split())


def check_body(text, label):
    c = Checker()
    c.feed(text)
    c.close()
    if c.stack:
        c.errors.append(f'не закрыты теги: {c.stack}')
    if c.errors:
        fail(f'{label}: ' + '; '.join(c.errors[:8]))
    if c.words < 400:
        fail(f'{label}: всего {c.words} слов — статья слишком короткая')
    return c.words


def wrap_tables(text):
    text = re.sub(r'<div class="tbl">\s*(<table)', r'\1', text)
    text = re.sub(r'(</table>)\s*</div>', r'\1', text)
    return text.replace('<table', '<div class="tbl"><table').replace('</table>', '</table></div>')


def human_date(d, lang):
    if lang == 'ru':
        return f'{d.day} {MONTHS_RU[d.month - 1]} {d.year}'
    return d.strftime('%B ') + str(d.day) + d.strftime(', %Y')


def render(lang, slug, d, title, desc, body, words, today):
    tpl = (TPL / f'article.{lang}.html').read_text(encoding='utf-8')
    path = f'/articles/{slug}/' if lang == 'ru' else f'/en/articles/{slug}/'
    ld = {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': title, 'description': desc, 'inLanguage': lang,
        'datePublished': d.isoformat(), 'dateModified': today.isoformat(),
        'mainEntityOfPage': SITE + path, 'image': SITE + '/og-image.jpg',
        'author': {'@type': 'Organization', 'name': 'CephFix', 'url': SITE + '/'},
        'publisher': {'@type': 'Organization', 'name': 'CephFix', 'url': SITE + '/',
                      'logo': {'@type': 'ImageObject', 'url': SITE + '/favicon-192.png'}},
    }
    rep = {
        '{{TITLE}}': html.escape(title), '{{DESC}}': html.escape(desc), '{{SLUG}}': slug,
        '{{DATE}}': d.isoformat(), '{{DATE_HUMAN}}': human_date(d, lang),
        '{{READ_MIN}}': str(max(1, round(words / 180))),
        '{{JSONLD}}': json.dumps(ld, ensure_ascii=False).replace('</', '<\\/'),
        '{{BODY}}': body,
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    if '{{' in tpl:
        fail(f'в шаблоне {lang} остались незаполненные поля')
    return path, tpl


def update_list(file, path, title, desc, d, lang):
    text = file.read_text(encoding='utf-8')
    item = (f'<li><a href="{path}"><b>{html.escape(title)}</b>'
            f'<span>{html.escape(desc)}</span><small>{human_date(d, lang)}</small></a></li>')
    text = re.sub(r'\n?<li><a href="' + re.escape(path) + r'">.*?</li>', '', text)
    text = text.replace('<!--LIST:START-->', '<!--LIST:START-->\n' + item, 1)
    text = re.sub(r'<!--EMPTY-->.*?<!--/EMPTY-->\n?\s*', '', text, flags=re.S)
    text = re.sub(r'\n?<meta name="robots" content="noindex"><!--EMPTY-NOINDEX-->', '', text)
    file.write_text(text, encoding='utf-8')


def update_sitemap(paths, today):
    f = ROOT / 'sitemap.xml'
    text = f.read_text(encoding='utf-8')
    for p in paths:
        loc = SITE + p
        if f'<loc>{loc}</loc>' in text:
            text = re.sub(r'(<loc>' + re.escape(loc) + r'</loc>\s*<lastmod>)[^<]*', r'\g<1>' + today.isoformat(), text)
        else:
            text = text.replace('</urlset>', f'  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today.isoformat()}</lastmod>\n  </url>\n</urlset>')
    f.write_text(text, encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        fail('укажите файл article.json')
    update = '--update' in sys.argv
    if not (ROOT / 'CNAME').exists() or not TPL.exists():
        fail('запускайте из корня репозитория сайта')
    meta_file = Path(sys.argv[1])
    meta = json.loads(meta_file.read_text(encoding='utf-8'))
    slug = meta.get('slug', '')
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', slug) or len(slug) > 80:
        fail(f'неправильный slug: {slug!r}')
    today = dt.date.today()
    d = dt.date.fromisoformat(meta['date']) if meta.get('date') else today

    out = {}
    for lang in ('ru', 'en'):
        m = meta.get(lang) or fail(f'нет раздела {lang}')
        title, desc = (m.get('title') or '').strip(), (m.get('description') or '').strip()
        if not title or len(title) > 110:
            fail(f'{lang}: заголовок пустой или длиннее 110 знаков')
        if not desc or len(desc) > 160:
            fail(f'{lang}: описание пустое или длиннее 160 знаков')
        body_path = Path(m['body'])
        if not body_path.is_absolute():
            body_path = meta_file.parent / body_path
        body = body_path.read_text(encoding='utf-8').strip()
        if re.search(r'<h1\b', body, re.I):
            fail(f'{lang}: уберите <h1> из тела — заголовок подставляет шаблон')
        body = wrap_tables(body)
        words = check_body(body, lang)
        out[lang] = (title, desc, body, words)

    target = ROOT / 'articles' / slug / 'index.html'
    if target.exists() and not update:
        fail(f'статья {slug} уже опубликована; для замены добавьте --update')

    changed = []
    paths = ['/articles/', '/en/articles/']
    for lang, (title, desc, body, words) in out.items():
        path, page = render(lang, slug, d, title, desc, body, words, today)
        f = ROOT / path.strip('/') / 'index.html'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page, encoding='utf-8')
        changed.append(str(f.relative_to(ROOT)))
        lst = ROOT / ('articles' if lang == 'ru' else 'en/articles') / 'index.html'
        update_list(lst, path, title, desc, d, lang)
        changed.append(str(lst.relative_to(ROOT)))
        paths.append(path)

    update_sitemap(paths, today)
    changed.append('sitemap.xml')

    main_page = ROOT / 'index.html'
    text = main_page.read_text(encoding='utf-8')
    if any(k in text for k in MARKERS):
        for k, v in MARKERS.items():
            text = text.replace(k, v)
        main_page.write_text(text, encoding='utf-8')
        changed.append('index.html (ссылка «Статьи» в меню)')

    print('Готово. Изменены файлы:')
    for c in changed:
        print('  ' + c)
    print(f'Адреса: {SITE}/articles/{slug}/  и  {SITE}/en/articles/{slug}/')


if __name__ == '__main__':
    main()
