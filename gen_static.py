# -*- coding: utf-8 -*-
"""
生成静态分享版工作台（GitHub Pages / 任意静态托管）
==================================================
在仓库根产出：
  index.html    static/index.html 的纯静态变体（library.json 加载数据、前端搜索、相对路径）
  library.json  条目 + 分类树 + 总结页纯文本（供前端搜索）
  .nojekyll     跳过 GitHub Pages 的 Jekyll 处理

本地 8766 服务不受影响（server 只映射 reports/ summaries/ static/，不会读根目录这两个文件）。
用法：python gen_static.py
"""
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import server  # 复用 scan_reports / build_tree / extract_html_text

STEXT_LIMIT = 30000  # 每条总结文本上限（字符），控制 library.json 体积


def build_library():
    items = server.scan_reports()
    tree = server.build_tree(items)
    for it in items:
        stext = ''
        if it['hasSummary']:
            rel = it['rel'] if it['rel'].startswith('summaries/') else \
                it['rel'].replace('reports/', 'summaries/', 1)[:-4] + '.html'
            stext = server.extract_html_text(os.path.join(BASE, rel), rel)
            stext = re.sub(r'\s+', ' ', stext).strip()
            if len(stext) > STEXT_LIMIT:
                stext = stext[:STEXT_LIMIT]
        it['stext'] = stext
    return {'total': len(items), 'reports': items, 'tree': tree}


STATIC_SEARCH_JS = '''async function fetchSearch(){
  const q = state.q.trim().toLowerCase();
  const results = [];
  for(const src of (LIB?LIB.reports:[])){
    if(state.org && src.org!==state.org) continue;
    if(state.from && src.date<state.from) continue;
    if(state.to && src.date>state.to) continue;
    const it = Object.assign({}, src);
    const hay = [src.title, src.org, src.category].join(' ').toLowerCase();
    if(!q){ results.push(it); continue; }
    if(hay.includes(q)){
      it.matchIn='meta'; it.snippet=src.title; it.offset=-1; it.rank=0;
      results.push(it); continue;
    }
    if(src.stext){
      const pos = src.stext.indexOf(q);
      if(pos>=0){
        const w=110, c=70;
        const s=Math.max(0,pos-c), e=Math.min(src.stext.length,pos+w);
        let frag=src.stext.slice(s,e).trim();
        it.matchIn='summary';
        it.snippet=(s>0?'…':'')+frag+(e<src.stext.length?'…':'');
        it.offset=pos-s+(s>0?3:0); it.rank=1;
        results.push(it);
      }
    }
  }
  if(!q) results.sort((a,b)=>(a.org+a.category).localeCompare(b.org+b.category));
  else results.sort((a,b)=>(a.rank||3)-(b.rank||3) || b.mtime-a.mtime);
  return {q: state.q, count: results.length, results: results};
}'''


def patch_ui(html):
    # 1) 数据源：本地 API → library.json
    html = html.replace("const r = await fetch('/api/library');",
                        "const r = await fetch('library.json');")
    html = html.replace("// /api/library 结果", "// library.json 结果（静态版）")
    # 2) 搜索：服务端 /api/search → 纯前端（标题/分类 + 总结文本）
    start = html.index('async function fetchSearch(){')
    end = html.index('\n}', start) + 2
    html = html[:start] + STATIC_SEARCH_JS + html[end:]
    # 3) 文件路径：/files/... → 相对路径（Pages 子路径友好）
    html = html.replace("function fileURL(rel){ return '/files/' + encPath(rel); }",
                        "function fileURL(rel){ return encPath(rel); }")
    assert 'library.json' in html and 'encPath(rel); }' in html and '/api/' not in html
    return html


def main():
    lib = build_library()
    with io.open(os.path.join(BASE, 'library.json'), 'w', encoding='utf-8') as f:
        json.dump(lib, f, ensure_ascii=False)
    with io.open(os.path.join(BASE, 'static', 'index.html'), encoding='utf-8') as f:
        ui = f.read()
    with io.open(os.path.join(BASE, 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(patch_ui(ui))
    with io.open(os.path.join(BASE, '.nojekyll'), 'w', encoding='utf-8') as f:
        f.write('')
    size = os.path.getsize(os.path.join(BASE, 'library.json'))
    print('OK: index.html + library.json (%.0f KB) + .nojekyll, %d 条' % (size / 1024, lib['total']))


if __name__ == '__main__':
    main()
