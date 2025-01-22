{
  "Comment": "DICOM Processing and Bedrock Inference Workflow",
  "StartAt": "Get Configuration",
  "States": {
    "Get Configuration": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:ssm:getParameters",
      "Parameters": {
        "Names": [
          "/dicom/network/subnet-ids",
          "/dicom/network/security-group-id",
          "/dicom/tasks/dicom-converter-task",
          "/dicom/tasks/bedrock-inference-task",
          "/dicom/storage/output-bucket",
          "/dicom/storage/inference-output-bucket",
          "/dicom/functions/layer-count-function",
          "/dicom/functions/aggregate-results-function"
        ],
        "WithDecryption": true
      },
      "ResultPath": "$.config",
      "Next": "Convert DICOM to Image Layers"
    },
    "Convert DICOM to Image Layers": {
      "Type": "Task",
      "Resource": "arn:aws:states:::ecs:runTask.sync",
      "Parameters": {
        "LaunchType": "FARGATE",
        "TaskDefinition.$": "$.config.Parameters[?(@.Name == '/dicom/tasks/dicom-converter-task')].Value[0]",
        "NetworkConfiguration": {
          "AwsvpcConfiguration": {
            "Subnets.$": "$.config.Parameters[?(@.Name == '/dicom/network/subnet-ids')].Value[0]",
            "SecurityGroups.$": "$.config.Parameters[?(@.Name == '/dicom/network/security-group-id')].Value[0]",
            "AssignPublicIp": "DISABLED"
          }
        },
        "Overrides": {
          "ContainerOverrides": [
            {
              "Name": "dicom-converter",
              "Environment": [
                {
                  "Name": "INPUT_BUCKET_NAME",
                  "Value.$": "$.bucket"
                },
                {
                  "Name": "INPUT_KEY",
                  "Value.$": "$.key"
                },
                {
                  "Name": "OUTPUT_BUCKET_NAME",
                  "Value.$": "$.config.Parameters[?(@.Name == '/dicom/storage/output-bucket')].Value[0]"
                }
              ]
            }
          ]
        }
      },
      "ResultPath": "$.conversionResult",
      "Next": "Get Layer Count"
    },
    "Get Layer Count": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.$": "$.config.Parameters[?(@.Name == '/dicom/functions/layer-count-function')].Value[0]",
        "Payload": {
          "outputBucket.$": "$.config.Parameters[?(@.Name == '/dicom/storage/output-bucket')].Value[0]",
          "outputPrefix.$": "$.conversionResult.OutputPrefix"
        }
      },
      "ResultPath": "$.layerCount",
      "Next": "Process Layers"
    },
    "Process Layers": {
      "Type": "Map",
      "InputPath": "$",
      "ItemsPath": "$.layerCount.Payload.layers",
      "MaxConcurrency": 5,
      "Iterator": {
        "StartAt": "Run Bedrock Inference",
        "States": {
          "Run Bedrock Inference": {
            "Type": "Task",
            "Resource": "arn:aws:states:::ecs:runTask.sync",
            "Parameters": {
              "LaunchType": "FARGATE",
              "TaskDefinition.$": "$.config.Parameters[?(@.Name == '/dicom/tasks/bedrock-inference-task')].Value[0]",
              "NetworkConfiguration": {
                "AwsvpcConfiguration": {
                  "Subnets.$": "$.config.Parameters[?(@.Name == '/dicom/network/subnet-ids')].Value[0]",
                  "SecurityGroups.$": "$.config.Parameters[?(@.Name == '/dicom/network/security-group-id')].Value[0]",
                  "AssignPublicIp": "DISABLED"
                }
              },
              "Overrides": {
                "ContainerOverrides": [
                  {
                    "Name": "bedrock-inference",
                    "Environment": [
                      {
                        "Name": "INPUT_BUCKET",
                        "Value.$": "$.config.Parameters[?(@.Name == '/dicom/storage/output-bucket')].Value[0]"
                      },
                      {
                        "Name": "INPUT_KEY",
                        "Value.$": "$$.Map.Item.Value"
                      },
                      {
                        "Name": "OUTPUT_BUCKET",
                        "Value.$": "$.config.Parameters[?(@.Name == '/dicom/storage/inference-output-bucket')].Value[0]"
                      }
                    ]
                  }
                ]
              }
            },
            "End": true
          }
        }
      },
      "Next": "Aggregate Results"
    },
    "Aggregate Results": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.$": "$.config.Parameters[?(@.Name == '/dicom/functions/aggregate-results-function')].Value[0]",
        "Payload": {
          "inferenceBucket.$": "$.config.Parameters[?(@.Name == '/dicom/storage/inference-output-bucket')].Value[0]",
          "inferencePrefix.$": "$.conversionResult.OutputPrefix"
        }
      },
      "End": true
    }
  }
}
