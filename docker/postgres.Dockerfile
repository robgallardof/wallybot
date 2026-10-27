FROM postgres:18.4-alpine
# Use Alpine's small privilege-drop helper instead of the upstream static Go binary.
# The official entrypoint calls `gosu postgres ...`; su-exec accepts the same invocation.
RUN apk upgrade --no-cache && apk add --no-cache su-exec \
    && rm /usr/local/bin/gosu
# Keep removal in its own layer so image analyzers see the old executable's deletion.
RUN printf '#!/bin/sh\nexec /sbin/su-exec "$@"\n' > /usr/local/bin/gosu \
    && chmod 755 /usr/local/bin/gosu
