cd /Users/uezerce/src/agrandiz.org && \
git ls-files -co --exclude-standard -z | \
tar --null -czf /tmp/agrandiz-repo-$(date +%Y%m%d-%H%M%S).tar.gz --files-from -
