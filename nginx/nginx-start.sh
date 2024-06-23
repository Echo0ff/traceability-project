#!/bin/sh

# Substitute environment variables in the nginx configuration template
envsubst '\$DOMAIN' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start nginx
nginx -g 'daemon off;'
