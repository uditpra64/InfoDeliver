# .venvの仮想環境を有効にして，Nuitkaを用いてアプリケーションをビルドするスクリプトです．

$ErrorActionPreference = "Stop"

# .venvの仮想環境をアクティベートする
Write-Host "仮想環境をアクティベートしています..."
& ".\.venv\Scripts\Activate.ps1"

# Nuitkaでアプリケーションをビルドする
Write-Host "Nuitkaでアプリケーションをビルド中..."
python -m nuitka --enable-plugin=pyqt6 --follow-imports --standalone --include-data-dir=data=data --include-data-dir=json=json --include-data-dir=rule=rule --include-data-file=.env=.env --include-package=langchain_community main.py

Write-Host "ビルドが完了しました．"