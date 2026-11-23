# ZORVEX HOSTING

Private single-owner file/process panel: upload, check, start, stop, restart, delete, live logs and Python requirements install.

## Safety
Only upload scripts you trust. Uploaded programs execute inside the same service container; this is not a hostile-code sandbox or multi-user hosting platform. Keep the service private and set a long random ADMIN_TOKEN in Render. Never put secrets in source code or share them in chat.

## Deploy
Create a Render Blueprint from this repository, set ADMIN_TOKEN and optionally OWNER_EMAIL. The blueprint configures a paid Starter Docker web service in Singapore and a 1 GB persistent disk. Free services may sleep and are not suitable for 24/7 processes. Review charges before creating paid resources.

Supported uploaded script types: .py, .js, .mjs, .java, .php, .sh. Manual install supports requirements.txt only.
