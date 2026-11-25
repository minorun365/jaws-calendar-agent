# JAWS-UG 東京イベントカレンダー登録エージェント

JAWS-UG 東京の勉強会を、JAWS-UG のイベントカレンダーへ自動で登録するエージェントです。毎日12時（日本時間）に connpass の直近のイベントを確認し、これから開催されるのにカレンダーへ載っていないものがあれば、登録用の Google フォームへ送信します。人に呼ばれなくても決まった時刻に自分で動く「アンビエントエージェント」として、Bedrock AgentCore Runtime と Strands Agents で作っています。

公開版は、そのままデプロイしてもフォームを送信せず、定期実行も停止した状態になっています。実際に使うときは、フォームのURLやカレンダーのAPIキーなどを CDK の context で渡して有効にします。フォームの記入者名は、エージェントが代わりに書いたと分かる名前にしており、既定は「みのるん（AgentCoreが代筆）」です。

## 構成

```mermaid
flowchart LR
  A["EventBridge Scheduler<br/>毎日 12:00 JST"] -->|"aws-sdk:bedrockagentcore:invokeAgentRuntime"| B["AgentCore Runtime<br/>Strands Agent"]
  B --> C["HTTP fetch<br/>connpass / JAWS-UG Calendar API"]
  B --> F["AgentCore Browser<br/>Google Form"]
  B --> D["DynamoDB<br/>処理済みイベント"]
  B --> E["Bedrock<br/>us Sonnet 4.6"]
```

Step Functions は使わず、EventBridge Scheduler の universal target で AgentCore Runtime を直接 invoke します。

## 初回レビュー用モード

- `preview_event`: connpass のイベント情報から Google フォームへ入力する値を返します。DynamoDB に処理済み状態を書き込まず、フォームも送信しません。
- `submit_approved_event`: `approved=true` と `FORM_SUBMIT_ENABLED=true` の両方が揃ったときだけ、指定された 1 件のフォームを送信します。

`dry_run` はフォーム送信予定値の確認専用で、DynamoDB に処理済み状態を残しません。

## 公開版の設定

公開リポジトリには実フォームURLと Google Calendar API key を含めていません。
デプロイ時に以下の context を指定します。

- `googleFormUrl`
- `jawsugCalendarApiKey`
- `formSubmitEnabled`
- `scheduleState`
- `submitterName`

詳細は [runbooks/deploy.md](runbooks/deploy.md) を参照してください。
