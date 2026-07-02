import { CfnOutput, RemovalPolicy, Stack, type StackProps } from "aws-cdk-lib";
import {
  AgentRuntimeArtifact,
  ProtocolType,
  Runtime as AgentCoreRuntime,
  RuntimeAuthorizerConfiguration,
  RuntimeNetworkConfiguration
} from "aws-cdk-lib/aws-bedrockagentcore";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Platform } from "aws-cdk-lib/aws-ecr-assets";
import { Effect, PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { CfnSchedule } from "aws-cdk-lib/aws-scheduler";
import { Construct } from "constructs";

export interface JawsugCalendarAgentStackProps extends StackProps {
  readonly formSubmitEnabled: boolean;
  readonly scheduleState: "ENABLED" | "DISABLED";
  readonly submitterName: string;
  readonly bedrockModelId: string;
  readonly connpassEventsUrl: string;
  readonly jawsugCalendarUrl: string;
  readonly jawsugCalendarId: string;
  readonly jawsugCalendarApiKey: string;
  readonly googleFormUrl: string;
}

export class JawsugCalendarAgentStack extends Stack {
  public constructor(scope: Construct, id: string, props: JawsugCalendarAgentStackProps) {
    super(scope, id, props);

    const stateTable = new Table(this, "StateTable", {
      tableName: "jawsug-calendar-agent-state",
      partitionKey: { name: "pk", type: AttributeType.STRING },
      sortKey: { name: "sk", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.RETAIN
    });

    const agentRuntime = new AgentCoreRuntime(this, "AgentRuntime", {
      runtimeName: "JawsugCalendarAgent",
      description: "Ambient agent that registers future JAWS-UG Tokyo connpass events to the JAWS-UG calendar form.",
      agentRuntimeArtifact: AgentRuntimeArtifact.fromAsset("agentcore-runtime", {
        platform: Platform.LINUX_ARM64
      }),
      protocolConfiguration: ProtocolType.HTTP,
      authorizerConfiguration: RuntimeAuthorizerConfiguration.usingIAM(),
      networkConfiguration: RuntimeNetworkConfiguration.usingPublicNetwork(),
      tracingEnabled: true,
      environmentVariables: {
        STATE_TABLE_NAME: stateTable.tableName,
        BEDROCK_REGION: Stack.of(this).region,
        BEDROCK_MODEL_ID: props.bedrockModelId,
        FORM_SUBMIT_ENABLED: props.formSubmitEnabled ? "true" : "false",
        SUBMITTER_NAME: props.submitterName,
        CONNPASS_EVENTS_URL: props.connpassEventsUrl,
        JAWSUG_CALENDAR_URL: props.jawsugCalendarUrl,
        JAWSUG_CALENDAR_ID: props.jawsugCalendarId,
        JAWSUG_CALENDAR_API_KEY: props.jawsugCalendarApiKey,
        GOOGLE_FORM_URL: props.googleFormUrl
      }
    });

    stateTable.grantReadWriteData(agentRuntime);
    agentRuntime.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:GetInferenceProfile"],
        resources: [
          Stack.of(this).formatArn({
            service: "bedrock",
            resource: "foundation-model",
            resourceName: "*",
            account: "",
            region: "*"
          }),
          Stack.of(this).formatArn({
            service: "bedrock",
            resource: "inference-profile",
            resourceName: "*",
            region: "*"
          })
        ]
      })
    );
    agentRuntime.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock-agentcore:*"],
        resources: ["*"]
      })
    );

    const schedulerRole = new Role(this, "SchedulerRole", {
      assumedBy: new ServicePrincipal("scheduler.amazonaws.com")
    });

    schedulerRole.addToPolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["bedrock-agentcore:InvokeAgentRuntime"],
        resources: [agentRuntime.agentRuntimeArn, `${agentRuntime.agentRuntimeArn}/runtime-endpoint/*`]
      })
    );

    new CfnSchedule(this, "DailyCheckSchedule", {
      name: "jawsug-calendar-agent-daily-check",
      description: "Invoke JAWS-UG calendar ambient agent every day at 12:00 JST.",
      flexibleTimeWindow: { mode: "OFF" },
      scheduleExpression: "cron(0 12 * * ? *)",
      scheduleExpressionTimezone: "Asia/Tokyo",
      state: props.scheduleState,
      target: {
        arn: "arn:aws:scheduler:::aws-sdk:bedrockagentcore:invokeAgentRuntime",
        roleArn: schedulerRole.roleArn,
        input: Stack.of(this).toJsonString({
          AgentRuntimeArn: agentRuntime.agentRuntimeArn,
          Qualifier: "DEFAULT",
          RuntimeSessionId: "jawsug-calendar-agent-daily-check",
          ContentType: "application/json",
          Payload: JSON.stringify({
            mode: "daily_check",
            dry_run: !props.formSubmitEnabled
          })
        })
      }
    });

    new CfnOutput(this, "AgentRuntimeArn", {
      value: agentRuntime.agentRuntimeArn
    });
    new CfnOutput(this, "StateTableName", {
      value: stateTable.tableName
    });
  }
}
