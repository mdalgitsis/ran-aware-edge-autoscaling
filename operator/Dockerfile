# builder stage unchanged
FROM golang:1.24-bullseye AS builder
ARG TARGETOS=linux
ARG TARGETARCH=amd64

WORKDIR /workspace
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/ cmd/
COPY api/ api/
COPY internal/ internal/

RUN apt-get update && apt-get install -y librdkafka-dev build-essential
ENV CGO_ENABLED=1

RUN GOOS=$TARGETOS GOARCH=$TARGETARCH go build -a -o manager cmd/main.go

# runtime stage
FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y librdkafka1 ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY --from=builder /workspace/manager .

USER 65532:65532
ENTRYPOINT ["/manager"]

