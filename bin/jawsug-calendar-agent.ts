#!/usr/bin/env node
import { App, Tags } from "aws-cdk-lib";
import { JawsugCalendarAgentStack } from "../lib/jawsug-calendar-agent-stack.js";

const app = new App();

const projectTag = app.node.tryGetContext("projectTag") as string | undefined;
Tags.of(app).add("Project", projectTag ?? "personal");

const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION ?? "us-east-1";
const env = account ? { account, region } : { region };

const formSubmitEnabled = (app.node.tryGetContext("formSubmitEnabled") as string | undefined) === "true";
const scheduleState = ((app.node.tryGetContext("scheduleState") as string | undefined) ?? "DISABLED") as
  | "ENABLED"
  | "DISABLED";
const submitterName = (app.node.tryGetContext("submitterName") as string | undefined) ?? "みのるん（AgentCoreが代筆）";
const bedrockModelId =
  (app.node.tryGetContext("bedrockModelId") as string | undefined) ?? "us.anthropic.claude-sonnet-4-6";
const connpassEventsUrl =
  (app.node.tryGetContext("connpassEventsUrl") as string | undefined) ?? "https://jawsug.connpass.com/event/";
const jawsugCalendarUrl =
  (app.node.tryGetContext("jawsugCalendarUrl") as string | undefined) ?? "https://jaws-ug.jp/calendar/";
const jawsugCalendarId =
  (app.node.tryGetContext("jawsugCalendarId") as string | undefined) ??
  "bm4nl4f76dop3h66n7a4ea67r8@group.calendar.google.com";
const jawsugCalendarApiKey = (app.node.tryGetContext("jawsugCalendarApiKey") as string | undefined) ?? "";
const googleFormUrl = (app.node.tryGetContext("googleFormUrl") as string | undefined) ?? "";

new JawsugCalendarAgentStack(app, "JawsugCalendarAgentStack", {
  env,
  formSubmitEnabled,
  scheduleState,
  submitterName,
  bedrockModelId,
  connpassEventsUrl,
  jawsugCalendarUrl,
  jawsugCalendarId,
  jawsugCalendarApiKey,
  googleFormUrl
});
