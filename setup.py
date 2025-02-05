from setuptools import setup, find_packages

setup(
    name='mao_epl',  # パッケージ名（pip listで表示される）
    version="0.1.0",  # バージョン
    description="EPL",  # 説明
    author='Shion Takeno',  # 作者名
    packages=find_packages(),  # 使うモジュール一覧を指定する
    #license='MIT'  # ライセンス
)