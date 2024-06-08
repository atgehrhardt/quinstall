```
mkdir -p openwebui && curl -L https://github.com/atgehrhardt/quinstall/archive/refs/heads/main.tar.gz | tar -xz -C openwebui --strip-components=2 quinstall-main/openwebui

python3 install.py
```