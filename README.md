AWS Lambda OptenTelemetry Logging
===============================

Simple log formatter to get Otel log records on stdout in an AWS lambda.

Trying to use a collector in AWS lambda runtime is stupid and doing so for [logging will lead to issues](https://github.com/aws-observability/aws-otel-lambda/issues/1121).

So the goal is simple:

- Write stuff that looks like OpenTelemetry, but uses AWS native services instead.
