proxy_pass http://backend:8000;
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $http_x_real_ip;
proxy_set_header X-Forwarded-For $http_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
proxy_connect_timeout 5s;
proxy_read_timeout 30s;
add_header Cache-Control no-store always;
