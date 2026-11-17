# _service_template

Skeleton for a new service. Copy it, then rename the folder and the `template_service` package
(it must end in `_service`; `scripts/check_boundaries.py` relies on that).

```
cp -r services/_service_template services/my_thing
mv services/my_thing/src/template_service services/my_thing/src/my_thing_service
# then fix imports/`service_name`, and add the service to docker-compose.yml + the CI matrix
```

Run: `uvicorn template_service.main:create_service_app --factory --reload` with
`PYTHONPATH=libs:services/_service_template/src`.
