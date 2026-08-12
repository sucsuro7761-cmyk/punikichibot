# punikichibot

妖怪ウォッチぷにぷに向けの便利機能Discord bot です。

## 現在の機能

### `/genki set current`

現在のゲンキ値を入力すると、全回復（最大値50固定）までの時間を計算し、
回復完了予定時刻にコマンドを打ったチャンネルで本人にメンション通知します。

- `GENKI_REGEN_MINUTES`（ゲンキが1回復するのにかかる分数）は `.env` で調整できます。デフォルトは5分です。実際のゲーム内の回復間隔に合わせて設定してください。
- `GENKI_MAX`（ゲンキの最大値）は `.env` で調整できます。デフォルトは50です。

### `/genki check`

設定中のタイマーの残り時間を確認します。

### `/genki cancel`

設定中のタイマーを取り消します。

> 注意: タイマーはメモリ上で管理しているため、botを再起動すると設定済みのタイマーは失われます。

### おたすけ募集

フレンドのボスに攻撃を頼める「おたすけ」の募集をパネルのボタンから行えます。

- `/otasuke panel`（管理者のみ）: 募集パネルを設置します。「通常で募集」「乱入で募集」の2つのボタンが表示され、押すと入力フォーム（キャラクターコード・詳細情報）が開きます。送信すると募集内容が投稿されます。
- `/otasuke setrole role:@ロール`（管理者のみ）: 募集が投稿されたときにメンションするロールを設定します。
- `/otasuke setchannel channel:#チャンネル`（管理者のみ）: 募集の投稿先チャンネルを設定します。未設定の場合はパネルのあるチャンネルに投稿されます。

> 注意: ロール・投稿先チャンネルの設定はメモリ上で管理しているため、botを再起動すると再設定が必要です。また、ロールへのメンションを実際に通知させるには、そのロールが「メンション可能」に設定されているか、botに「@everyone、@here、全てのロールにメンション」権限が必要です。

## セットアップ

### 1. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成
2. 「Bot」タブでBotを追加し、トークンを発行してコピー
3. 「OAuth2 > URL Generator」で以下を選択してサーバーに招待
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`（おたすけ募集の投稿に必要。ロールへのメンション通知が必要な場合は `Mention @everyone, @here, and All Roles` も付与してください）

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

起動後、Discordサーバーで `/genki` や `/otasuke` コマンドが使えるようになります
（反映まで数分かかる場合があります）。

## Railwayでのデプロイ

このリポジトリには `Procfile`（`worker: python bot.py`）を含めているため、
Railwayにリポジトリを接続するだけでビルド・起動コマンドを自動認識します。

- Railwayの Variables に `DISCORD_TOKEN`（と必要なら `GENKI_REGEN_MINUTES`）を設定してください（`.env` ファイルは不要です）。
- Webサーバーではなくbotプロセスなので、Railway側で公開URL/ヘルスチェックの設定は不要です。

## 今後の拡張予定

- 妖怪図鑑検索（外部サイトスクレイピング）
