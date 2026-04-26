# Terraform backend state (S3 + DynamoDB locking)
# Run `terraform init` in this directory after creating the backend resources:
#   aws s3 mb s3://simp-terraform-state-dev
#   aws dynamodb create-table --table-name simp-terraform-locks-dev \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST
