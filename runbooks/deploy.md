# Deploy

## 前提

- AWS profile: 任意
- AWS account: 任意
- Region: `us-east-1` を想定
- CDK deploy は CloudFormation Express mode を使う
- 記入者氏名は `みのるん（AgentCoreが代筆）`
- 公開リポジトリには実際の Google Form URL と Google Calendar API key を含めない

## 検証

```bash
npm install
npm run build
npm run synth
```

## デプロイ

最初は Google フォーム送信と Scheduler を無効にしてデプロイする。

```bash
export AWS_PROFILE=<your-profile>
AWS_REGION=us-east-1 \
AWS_DEFAULT_REGION=us-east-1 \
CDK_DEFAULT_ACCOUNT=<your-account-id> \
CDK_DEFAULT_REGION=us-east-1 \
npx cdk deploy --all --express --require-approval never \
  -c projectTag=personal \
  -c formSubmitEnabled=false \
  -c scheduleState=DISABLED \
  -c googleFormUrl='<google-form-url>' \
  -c jawsugCalendarApiKey='<google-calendar-api-key>' \
  -c 'submitterName=みのるん（AgentCoreが代筆）'
```

## 実送信を有効化する場合

外部の Google フォームへ送信するため、リリース前の初回は必ず 1 件だけレビューする。

1. `preview_event` の結果をレビュー担当者へ共有する。
2. レビュー担当者から送信の承認を得る。
3. Scheduler は `DISABLED` のまま、`formSubmitEnabled=true` でデプロイする。
4. `submit_approved_event` を 1 件だけ invoke する。
5. 送信結果を確認する。

```bash
export AWS_PROFILE=<your-profile>
AWS_REGION=us-east-1 \
AWS_DEFAULT_REGION=us-east-1 \
CDK_DEFAULT_ACCOUNT=<your-account-id> \
CDK_DEFAULT_REGION=us-east-1 \
npx cdk deploy --all --express --require-approval never \
  -c projectTag=personal \
  -c formSubmitEnabled=true \
  -c scheduleState=DISABLED \
  -c googleFormUrl='<google-form-url>' \
  -c jawsugCalendarApiKey='<google-calendar-api-key>' \
  -c 'submitterName=みのるん（AgentCoreが代筆）'
```

初回の送信レビューが終わったあと、日次運用を始めるときだけ `scheduleState=ENABLED` で再デプロイする。
