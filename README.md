# punikichibot

妖怪ウォッチぷにぷに向けの便利機能Discord bot です。

## 現在の機能

### `/genki set current target`

現在のゲンキ値を入力すると、指定した目標値（`target`、省略時は最大値50）まで貯まるまでの時間を計算し、
到達予定時刻にコマンドを打ったチャンネルで本人にメンション通知します。

- `target` は省略可能です。省略した場合は最大値（デフォルト50）まで貯まった時点で通知します。
- `GENKI_REGEN_MINUTES`（ゲンキが1回復するのにかかる分数）は `.env` で調整できます。デフォルトは5分です。実際のゲーム内の回復間隔に合わせて設定してください。
- `GENKI_MAX`（ゲンキの最大値）は `.env` で調整できます。デフォルトは50です。

### `/genki check`

設定中のタイマーの残り時間を確認します。

### `/genki cancel`

設定中のタイマーを取り消します。

> 注意: タイマーはメモリ上で管理しているため、botを再起動すると設定済みのタイマーは失われます。

### おたすけ募集

フレンドのボスに攻撃を頼める「おたすけ」の募集をパネルのボタンから行えます。
種別は「通常」「乱入（LV1〜4）」「乱入（LV5〜8）」「乱入（LV9〜）」の4つに分かれており、
それぞれ個別にメンションロール・投稿先チャンネルを設定できます。

- `/otasuke panel`（管理者のみ）: 募集パネルを設置します。「通常で募集」「乱入で募集」の2つのボタンが表示されます。
  - 「通常で募集」: 入力フォーム（キャラクターコード・詳細情報）が開きます。
  - 「乱入で募集」: 入力フォーム（ボスのレベル・キャラクターコード・詳細情報）が開きます。入力したレベルによって自動で「乱入（LV1〜4）」「乱入（LV5〜8）」「乱入（LV9〜）」に振り分けられます。
  - キャラクターコードは半角数字・小文字アルファベットのみ入力可能です（それ以外の文字を含むとエラーになり再入力を求められます）。
  - 投稿はコードブロック表記（`` `code` ``）で表示され、タップ・クリックですぐコピーできます。
  - 埋め込み内に募集者のメンションが表示されます。
- `/otasuke setrole category:種別 role:@ロール`（管理者のみ）: 指定した種別の募集時にメンションするロールを設定します。
- `/otasuke setchannel category:種別 channel:#チャンネル`（管理者のみ）: 指定した種別の募集の投稿先チャンネルを設定します。未設定の種別はパネルのあるチャンネルに投稿されます。
- `/otasuke sync`（管理者のみ）: 「おたすけ募集」カテゴリと、4種別分のテキストチャンネルを自動作成し、それぞれを対応する種別の投稿先として自動設定します。既に同名のチャンネルがある場合はそれを再利用します。

> 注意: ロール・投稿先チャンネルの設定はメモリ上で管理しているため、botを再起動すると再設定（または `/otasuke sync` の再実行）が必要です。また、ロールへのメンションを実際に通知させるには、そのロールが「メンション可能」に設定されているか、botに「@everyone、@here、全てのロールにメンション」権限が必要です。`/otasuke sync` を使うにはbotに「チャンネルの管理」権限が必要です。

#### 予約投稿

指定した日時になったら自動でおたすけ募集を投稿する予約機能です。

- `/otasuke reserve category:種別 time:時刻 character_code:コード level:レベル(乱入のみ必須) details:詳細(任意)`: 指定した日時に自動で募集を投稿するよう予約します。`time` は `21:00`（今日または明日のその時刻）または `10/05 21:00`（日付指定、日本時間）の形式で指定します。
- `/otasuke reservations`: 自分が予約中の募集の一覧（ID・種別・予約時刻）を確認します。
- `/otasuke cancelreserve reservation_id:ID`: 指定したIDの予約を取り消します。

> 注意: 予約もメモリ上で管理しているため、botを再起動すると予約は失われます。予約時刻になった時点で投稿先チャンネルが見つからない場合は、予約時に実行したチャンネルにエラーメッセージが送信されます。

## セットアップ

### 1. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成
2. 「Bot」タブでBotを追加し、トークンを発行してコピー
3. 「OAuth2 > URL Generator」で以下を選択してサーバーに招待
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`（おたすけ募集の投稿に必要。ロールへのメンション通知が必要な場合は `Mention @everyone, @here, and All Roles` も、`/otasuke sync` でチャンネルを自動作成する場合は `Manage Channels` も付与してください）

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
