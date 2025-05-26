DEPLOY AGENT:

```
python deployer.py --agent ../deployer/agents/conversational
```


RUN A DOCKER:

```
cd out_{agent_name}
docker build -t langchain-agent-api .
docker run -p 5005:5005 --env-file .env langchain-agent-api
```