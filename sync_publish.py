# -*- coding: utf-8 -*-
"""
宏观报告工作台 · 双机协作发布（2026-11-25 用户定稿：两台电脑都在更新，必须合并而非覆盖）
==============================================================================
标准发布流程（本脚本全自动）：
  1. 先提交本地批次（归档+总结的新文件）
  2. git fetch + pull --rebase（把另一台电脑的提交合并进来；-X ours 仅用于
     library.json/index.html 这类本机随即便可再生成的生成物，报告文件保持双方并集）
  3. 重新生成静态分享版（gen_static.py）——此时数据 = 两台电脑的并集
  4. 提交静态版刷新（如有变化）
  5. push origin（SSH 22 → 443 自动降级重试；被拒则再 pull --rebase 后重来）
  6. push gitee 镜像

铁律：
  - 永远不允许 force push（会吃掉另一台电脑的报告）
  - 推送前必须先 pull --rebase（合作 = 并集）
  - 同名文件冲突（两台机归档同一报告）时 -X ours 取本机版并在输出里警告，人工复核
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.stdout.reconfigure(encoding='utf-8')

URL_22 = 'origin'
URL_443 = 'ssh://git@ssh.github.com:443/lianrkcnd/bigrabbit-report.git'
GITEE = 'gitee'


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        class _R:  # 超时按失败处理
            returncode, stdout, stderr = -9, '', f'timeout after {timeout}s'
        return _R()


def head():
    return run(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip()


def fetch(remote_url):
    """fetch；SSH 22 失败自动降级 443。返回 (ok, fetched_head)。"""
    for url in (remote_url, URL_443):
        for attempt in (1, 2, 3):
            r = run(['git', 'fetch', url, 'main'], timeout=90)
            if r.returncode == 0:
                head = run(['git', 'rev-parse', 'FETCH_HEAD']).stdout.strip()
                return True, head
        print(f'  fetch 经 {url.split("//")[-1].split("/")[0]} 失败，换通道重试…')
    return False, None


def main():
    msg = ' '.join(sys.argv[1:]) or '批量归档+总结更新'
    print('== [1/5] 提交本地批次 ==')
    r = run(['git', 'add', '-A'])
    r = run(['git', 'commit', '-m', msg])
    print('  ', head(), msg if r.returncode == 0 else '无新改动')

    print('== [2/5] 拉取并合并另一台电脑的更新（pull --rebase）==')
    ok, remote_head = fetch(URL_22)
    if not ok:
        print('FAIL: GitHub 当前完全不可达，本地提交已安全保存；稍后重跑本脚本即可')
        sys.exit(1)
    local = head()
    if local == remote_head:
        print('  已是最新，无对方新提交')
    else:
        behind = run(['git', 'log', '--oneline', f'{local}..{remote_head}']).stdout.strip()
        ahead = run(['git', 'log', '--oneline', f'{remote_head}..{local}']).stdout.count('\n') + 1
        print('  对方新提交：')
        for line in behind.splitlines():
            print('   ', line)
        r = run(['git', 'rebase', remote_head])
        if r.returncode != 0:
            conflicts = run(['git', 'diff', '--name-only', '--diff-filter=U']).stdout.strip()
            print('FAIL: rebase 冲突，涉及：', conflicts)
            print('  处理原则：报告文件若两边都归档了同一份，保留内容更完整的一边后')
            print('  git add <文件> && git rebase --continue；或跑 git rebase --abort 放弃本次')
            sys.exit(1)
        print(f'  合并完成，本地 {ahead} 个提交已变基到对方之上 -> {head()}')

    print('== [3/5] 重新生成静态分享版（数据=双方并集）==')
    r = run([r'C:/Users/连瑞康/.workbuddy/binaries/python/envs/default/Scripts/python.exe',
             'gen_static.py'], timeout=300)
    print('  ', (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else '?')

    print('== [4/5] 提交静态版刷新 ==')
    run(['git', 'add', '-A'])
    r = run(['git', 'commit', '-m', '刷新静态分享版（双机合并后重新生成）'])
    print('  ', head(), '已提交' if r.returncode == 0 else '无变化')

    print('== [5/5] 推送 GitHub + Gitee ==')
    for remote in (URL_22, GITEE):
        pushed = False
        for attempt in (1, 2, 3):
            url = URL_443 if (remote == URL_22 and attempt > 1) else remote
            r = run(['git', 'push', url, 'main'], timeout=180)
            if r.returncode == 0:
                print(f'  push {remote} OK')
                pushed = True
                break
            out = (r.stdout + r.stderr)
            if 'rejected' in out or 'non-fast-forward' in out:
                print('  远端又有新提交，重新拉取合并…')
                ok2, rh = fetch(URL_22)
                if ok2:
                    run(['git', 'rebase', rh])
                    run([r'C:/Users/连瑞康/.workbuddy/binaries/python/envs/default/Scripts/python.exe',
                         'gen_static.py'])
                    run(['git', 'add', '-A'])
                    run(['git', 'commit', '-m', '刷新静态分享版（再次合并后重新生成）'])
                continue
        if not pushed:
            print(f'  push {remote} 三次失败——本地一切已保存，稍后重跑本脚本')
    print('完成。线上: https://lianrkcnd.github.io/bigrabbit-report/')


if __name__ == '__main__':
    main()
