# `source source-env.sh` to make plain `aws ...` commands work against
# LocalStack and ignore your global ~/.aws/config (which has a corrupted
# region entry).
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_REGION=us-east-1
unset AWS_PROFILE

# Convenience alias: aws_ls = aws against LocalStack
aws_ls() { command aws --endpoint-url http://localhost:4566 "$@"; }
echo "env set. use:    aws_ls s3 ls"
echo "                 aws_ls lambda list-functions"
echo "                 aws_ls logs describe-log-groups"
