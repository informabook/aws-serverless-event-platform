from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_evt,
    aws_sns as sns,                       # NOUVEAU
    aws_sns_subscriptions as subs         # NOUVEAU
)
from constructs import Construct

class GlobalEventProjectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # === 1. VPC ===
        self.vpc = ec2.Vpc(self, "GlobalEventVPC", max_azs=2, nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)
            ]
        )
        
        # Endpoints
        self.vpc.add_gateway_endpoint("DynamoDBEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)
        vpce_sg = ec2.SecurityGroup(self, "EndpointSG", vpc=self.vpc)
        vpce_sg.add_ingress_rule(ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.tcp(443))
        
        self.vpc.add_interface_endpoint("SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED), security_groups=[vpce_sg]
        )
        self.vpc.add_interface_endpoint("SQSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS, private_dns_enabled=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED), security_groups=[vpce_sg]
        )

        # === 2. DATA ===
        self.events_table = dynamodb.Table(self, "EventsTable",
            partition_key=dynamodb.Attribute(name="event_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.DESTROY
        )

        self.orders_queue = sqs.Queue(self, "OrdersQueue", visibility_timeout=Duration.seconds(30))

        self.db_sg = ec2.SecurityGroup(self, "DBSecurityGroup", vpc=self.vpc)
        self.db_sg.add_ingress_rule(ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.tcp(5432))
        self.postgres_db = rds.DatabaseInstance(self, "GlobalEventDB",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_14),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[self.db_sg], database_name="globaleventdb",
            allocated_storage=20, max_allocated_storage=20, publicly_accessible=False,
            removal_policy=RemovalPolicy.DESTROY, deletion_protection=False
        )

        # === 3. LAMBDAS ===
        sql_layer = _lambda.LayerVersion(self, "Psycopg2Layer", code=_lambda.Code.from_asset("layers"), compatible_runtimes=[_lambda.Runtime.PYTHON_3_9])

        # A. Backend API
        self.backend_lambda = _lambda.Function(self, "GlobalEventBackend",
            runtime=_lambda.Runtime.PYTHON_3_9, handler="main.handler",
            code=_lambda.Code.from_asset("lambda"), vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            layers=[sql_layer],
            environment={
                "TABLE_NAME": self.events_table.table_name,
                "DB_SECRET_NAME": self.postgres_db.secret.secret_name,
                "DB_PROXY_ENDPOINT": self.postgres_db.db_instance_endpoint_address,
                "QUEUE_URL": self.orders_queue.queue_url
            }, timeout=Duration.seconds(30)
        )
        
        self.events_table.grant_read_write_data(self.backend_lambda)
        self.postgres_db.secret.grant_read(self.backend_lambda)
        self.postgres_db.connections.allow_from(self.backend_lambda, ec2.Port.tcp(5432))
        self.orders_queue.grant_send_messages(self.backend_lambda)

        # --- NOUVEAU : SNS TOPIC ---
        # C'est ici qu'on crée le "Sujet" de notification
        self.notification_topic = sns.Topic(self, "OrderNotificationTopic",
            display_name="GlobalEvent Alerts"
        )

        user_email = self.node.try_get_context("email")

        if not user_email:
            # Si l'utilisateur oublie le paramètre, on lève une erreur explicite
            raise ValueError("❌ ERREUR: Vous devez fournir un email pour les notifications.\nUsage: cdk deploy -c email=votre@email.com")

        self.notification_topic.add_subscription(
            subs.EmailSubscription(user_email)
        )

        # B. Email Worker
        self.email_worker = _lambda.Function(self, "EmailWorker",
            runtime=_lambda.Runtime.PYTHON_3_9, handler="email_worker.handler",
            code=_lambda.Code.from_asset("lambda"),
            environment={
                "SNS_TOPIC_ARN": self.notification_topic.topic_arn # On lui donne l'adresse du Topic
            }
        )
        
        self.email_worker.add_event_source(lambda_evt.SqsEventSource(self.orders_queue))
        
        # On donne le droit au Worker de publier sur SNS
        self.notification_topic.grant_publish(self.email_worker)

        # === 4. API GATEWAY ===
        self.api = apigw.LambdaRestApi(self, "GlobalEventAPI", handler=self.backend_lambda, proxy=True,
            default_cors_preflight_options=apigw.CorsOptions(allow_origins=apigw.Cors.ALL_ORIGINS, allow_methods=apigw.Cors.ALL_METHODS)
        )

        # === 5. FRONTEND ===
        website_bucket = s3.Bucket(self, "WebsiteBucket", removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True, block_public_access=s3.BlockPublicAccess.BLOCK_ALL)
        origin_identity = cloudfront.OriginAccessIdentity(self, "CloudFrontOAI")
        website_bucket.grant_read(origin_identity)
        distribution = cloudfront.Distribution(self, "GlobalEventDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(website_bucket, origin_access_identity=origin_identity),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(http_status=403, response_http_status=200, response_page_path="/index.html"),
                cloudfront.ErrorResponse(http_status=404, response_http_status=200, response_page_path="/index.html")
            ]
        )
        s3deploy.BucketDeployment(self, "DeployWebsite", sources=[s3deploy.Source.asset("frontend")], destination_bucket=website_bucket, distribution=distribution, distribution_paths=["/*"])

        CfnOutput(self, "ApiUrl", value=self.api.url)
        CfnOutput(self, "WebsiteUrl", value=distribution.distribution_domain_name)