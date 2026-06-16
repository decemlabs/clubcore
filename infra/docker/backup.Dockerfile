# backup.Dockerfile — purpose-built backup tooling image (CR-02 / BAK-02 / BAK-04)
#
# CR-02: the Redis RDB and SeaweedFS mirror CronJobs run under the SEC-03 hardened
# securityContext (readOnlyRootFilesystem: true). Installing packages at runtime
# via `apk add aws-cli` is impossible on a read-only rootfs, so every scheduled run
# failed at startup. This image PRE-BAKES the required CLIs so no runtime install is
# needed and readOnlyRootFilesystem: true is preserved.
#
# Tools shipped:
#   - redis-cli (BGSAVE / LASTSAVE / --rdb dump)  → from the redis-tools alpine package
#   - aws-cli   (s3 cp / s3 sync / s3api)         → from the aws-cli alpine package
#   - coreutils (GNU date -d for retention math)  → portable date arithmetic
#
# IMG-04: built and tagged with the git short-SHA by infra/scripts/build-images.sh,
# pinned via Helm values (backup.image.repository + global image.tag). No latest tags.
#
# Runs as the SEC-03 non-root user (uid 1000). Only /tmp (and, for the mirror job,
# /mnt/backup) are writable via emptyDir / PVC mounts.

FROM alpine:3.20

# redis (provides redis-cli), aws-cli for S3, coreutils for GNU `date -d`.
RUN apk add --no-cache redis aws-cli coreutils ca-certificates \
    && adduser -D -u 1000 backup

USER 1000
ENTRYPOINT ["/bin/sh"]
