import asyncio
from app.api import auth
from pathlib import Path

async def main():
    auth.settings.UPLOAD_DIR = './uploads'
    email = 'you+localtest@example.test'
    name = 'Local Test'
    link = 'https://local.test/activate?token=devtoken'
    print('UPLOAD_DIR ->', auth.settings.UPLOAD_DIR)
    ok = await auth.send_activation_email(email, name, link)
    print('send_activation_email returned ->', ok)
    dump_dir = Path(auth.settings.UPLOAD_DIR) / 'sent_emails'
    if dump_dir.exists():
        files = sorted(dump_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:3]:
            print('FOUND:', f)
            print(f.read_text(encoding='utf-8')[:800])
    else:
        print('no dump_dir found at', dump_dir.resolve())

if __name__ == '__main__':
    asyncio.run(main())
