if exist ./.venv (./.venv/Script/activate) else (
                                                 python -m venv .venv
                                                 ./.venv/Script/activate
                                                 pip install -r requirements.txt)
