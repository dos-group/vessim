## Local Sphinx Docs Build

From the vessim TLD run either
- w/ bash:
```bash
pip install .[docs]
```
- w/ zsh:
```zsh
pip install '.[docs]'
```

Then from within the `docs` dir:
```
make html
```
Open `_build/html/index.html` in your browser.

Sometimes, when, e.g. changing the toctrees, some changes may not be reflected
correctly on all sites. Simply delete the `_build` dir and build again.