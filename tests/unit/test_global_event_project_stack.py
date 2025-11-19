import aws_cdk as core
import aws_cdk.assertions as assertions

from global_event_project.global_event_project_stack import GlobalEventProjectStack

# example tests. To run these tests, uncomment this file along with the example
# resource in global_event_project/global_event_project_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = GlobalEventProjectStack(app, "global-event-project")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
