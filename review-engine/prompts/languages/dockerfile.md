Dockerfile 검토 시 특히 아래를 중요하게 봅니다.

- base image pinning과 build reproducibility
- root runtime, secret leakage, broad COPY scope
- layer hygiene와 install/cache 전략
