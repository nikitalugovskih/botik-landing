FROM nginx:alpine

RUN apk add --no-cache gettext

COPY site /usr/share/nginx/html

CMD sh -c "envsubst < /usr/share/nginx/html/review.template.html > /usr/share/nginx/html/review.html && nginx -g 'daemon off;'"
