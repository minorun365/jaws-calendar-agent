# Design

## 決定

- EventBridge Scheduler から AgentCore Runtime を直接 invoke する。
- Step Functions は使わない。
- region は `us-east-1` を想定する。
- CDK deploy は `--express` を使う。
- 重複防止は DynamoDB の条件付き書き込みで行う。
- 初回は `FORM_SUBMIT_ENABLED=false` で送信不可とする。
- リリース前の初回だけ、1 件分のフォーム入力値を提示し、承認後に手動で `submit_approved_event` を invoke する。
- connpass の未来イベント抽出は HTTP fetch + HTML パースを優先し、失敗した場合だけ AgentCore Browser + Strands へフォールバックする。
- JAWS-UG 公式カレンダーは FullCalendar + 公開 Google Calendar フィードなので、重複チェックは公開フィードを先に見て、失敗した場合だけ AgentCore Browser でページ確認する。

## 重複防止

connpass URL の `/event/{id}/` から `event_id` を取り、DynamoDB の `EVENT#{event_id}` を主キーにする。

`attribute_not_exists(pk)` で予約できたイベントだけ、JAWS-UG カレンダー確認とフォーム入力へ進める。
`DRY_RUN` や `FAILED`、30 分以上前の stale な `RESERVED` は再予約できる。

`dry_run` は DynamoDB に処理済み状態を書かない。これは dry run 後に本番化したとき、未送信イベントが「既処理」と見なされる事故を避けるため。

カレンダー確認:

- `https://jaws-ug.jp/calendar/` の `/assets/js/calendar.js` から参照されている Google Calendar ID を使う。
- 同日イベントを取得し、connpass URL またはタイトル一致で既登録判定する。
- API 取得に失敗した場合は、従来どおり AgentCore Browser + Strands でページ確認する。

## 初回レビュー

手順:

1. `preview_event` でフォーム入力予定値を作る。
2. 「開催地域名」「勉強会名」「日付」「開始時刻」「終了時刻」「場所」「イベントURL」「記入者氏名」を共有する。
3. 送信してよいか明示承認を得る。
4. Scheduler は `DISABLED` のまま、`FORM_SUBMIT_ENABLED=true` にして `submit_approved_event` を 1 件だけ実行する。
5. 初回送信結果を確認してから、日次運用を有効化する。

記入者氏名は必ず `みのるん（AgentCoreが代筆）` とする。

## 参考

- EventBridge Scheduler universal target: https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html
