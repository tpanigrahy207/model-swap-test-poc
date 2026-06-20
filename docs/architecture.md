# Architecture

`core/` defines the durable contracts and engine. It must not contain endpoint-specific identifiers or import adapter modules.

`adapters/` contains endpoint-specific calling code.

`profiles/models.profile.yaml` maps endpoint ids to adapter classes, hosts, environment variables, and model identifiers. It is the refreshable implementation profile.

`profiles/capabilities/` defines business capabilities. A capability is evaluated against its own acceptance criteria, not against the incumbent endpoint's output style.

`evals/` contains evidence. Each eval call produces a `RouteRecord`, closing the learning loop with durable state.
