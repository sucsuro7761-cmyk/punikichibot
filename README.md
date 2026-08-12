# punikichibot

妖怪ウォッチぷにぷに向けの便利機能Discord bot です。

## 現在の機能

### `/genki set current max`

現在のげんき値と最大値を入力すると、全回復までの時間を計算し、
回復完了予定時刻にコマンドを打ったチャンネルで本人にメンション通知します。

- `GENKI_REGEN_MINUTES`（げんきが1回復するのにかかる分数）は `.env` で調整できます。デフォルトは3分です。実際のゲーム内の回復間隔に合わせて設定してください。

### `/genki check`

設定中のタイマーの残り時間を確認します。

### `/genki cancel`

設定中のタイマーを取り消します。

> 注意: タイマーはメモリ上で管理しているため、botを再起動すると設定済みのタイマーは失われます。

## セットアップ

### 1. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成
2. 「Bot」タブでBotを追加し、トークンを発行してコピー
3. 「OAuth2 > URL Generator」で以下を選択してサーバーに招待
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`

### 2. 環境構築

```bash
python -m venv venv
source venv/bin/activate  # Windowsの場合は venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` を編集し、`DISCORD_TOKEN` に発行したトークンを設定してください。

### 3. 起動

```bash
python bot.py
```

起動後、Discordサーバーで `/genki` コマンドが使えるようになります
（反映まで数分かかる場合があります）。

## Railwayでのデプロイ

このリポジトリには `Procfile`（`worker: python bot.py`）を含めているため、
Railwayにリポジトリを接続するだけでビルド・起動コマンドを自動認識します。

- Railwayの Variables に `DISCORD_TOKEN`（と必要なら `GENKI_REGEN_MINUTES`）を設定してください（`.env` ファイルは不要です）。
- Webサーバーではなくbotプロセスなので、Railway側で公開URL/ヘルスチェックの設定は不要です。

## 今後の拡張予定

- 妖怪図鑑検索（外部サイトスクレイピング）
