"""将密钥保存在仅当前账户可读写的本地文件中。"""
import getpass
import json
import os
from pathlib import Path


def main():
    key = getpass.getpass('输入 DeepSeek API Key（输入隐藏）: ').strip()
    if not key:
        raise SystemExit('未输入密钥，未修改配置。')
    path = Path(__file__).resolve().parent / '.local-key.json'
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump({'api_key': key}, handle)
    print('已保存本地配置。以后运行无需重复输入。请勿分享 .local-key.json。')


if __name__ == '__main__':
    main()
