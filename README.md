# profilekit（アカウント開設キット）

新しいアカウントを作るときの「名前候補＋アイコン画像＋自己紹介文」を、1画面でセット生成する小さな Web ツールです。

既存作品 accountnamemaker（名前候補生成）と accountimagemaker（seed 式アイコン生成）の合体版という位置づけです。各候補のアイコンは、その名前文字列から決定的に導いた seed で生成するため、同じ名前＋同じスタイルではいつも同じ画像になります。

## 機能

- テーマを選んで名前候補を6件生成
  - テーマ：かわいい／かっこいい／自然・和風／おしゃれ／ゲーム風／食べ物・カフェ／宇宙・星／おまかせ
  - キーワード（任意）を入れると、候補すべてにその言葉が反映されます
  - 「数字をつける」のオン／オフに対応
  - 名前は小文字英数と `_` `.` のみに整形されます
- 各候補にアイコン画像を添えてカード表示
  - スタイル：identicon（5×5ブロック）／geometric（幾何学模様）／pixel（ドット絵フェイス）
  - アイコンは名前のハッシュから決定的に生成され、再現性があります
- 各候補に自己紹介文テンプレを添えて表示
  - テンプレはテーマ別に3パターン以上を用意し、名前に応じて決定的に選ばれます
- DB なし。依存は Flask + Pillow + gunicorn のみ

## 使い方

1. テーマ・キーワード・アイコンのスタイル・数字の有無を選ぶ
2. 「キットを生成」を押す
3. 名前＋アイコン＋自己紹介文の候補6件がカードで表示される
4. 気に入った名前のアイコンは `/icon?name=<名前>&style=<スタイル>` で直接取得・保存できます

※ 候補が各サービスで実際に使えるか（空き状況）は確認していません。登録前にサービス側で確認してください。

## エンドポイント

| パス | 説明 |
|---|---|
| `GET /` | 入力フォーム |
| `POST /generate`（`GET` も可） | 候補キットを生成して表示 |
| `GET /icon?name=<name>&style=<style>` | 名前から決定的に生成したアイコン PNG |
| `GET /healthz` | `{"status": "ok"}` |

## ローカル実行

```bash
pip install -r requirements.txt
python app.py
# http://localhost:5000
```

## テスト

```bash
python -m unittest discover -s tests
```

## Render デプロイ

`render.yaml` を同梱しています。Render でこのリポジトリを Web Service として作成すると、無料プランでデプロイできます。

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Health Check Path: `/healthz`

## ライセンス

MIT License（`LICENSE` を参照）
