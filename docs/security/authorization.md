# Brain Authorization Contract

Brain authorization is server-side and deny-by-default. Provider claims may identify a verified user, but Brain's own membership, role and resource-grant records decide what that user may access.

## Evaluation order

1. Verify the authenticated Brain user.
2. Require an active user account.
3. Require membership in the requested organisation. A non-member receives `404` so the tenant/resource is not disclosed.
4. Check the role permission matrix. A member whose role lacks the capability receives `403`.
5. For a restricted resource, require an explicit user grant before the endpoint body runs. Missing grants return `404`.
6. Only after those checks may route code call a connector, search service, LLM or tool.

This order is mandatory for future Slack, GitHub, document, search and AI routes.

## Role matrix

| Permission | Owner | Admin | Executive | Manager | Member | Guest |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Organisation read | yes | yes | yes | yes | yes | yes |
| Membership read | yes | yes | yes | yes | yes | no |
| Membership manage | yes | yes | no | no | no | no |
| Resource read capability | yes | yes | yes | yes | yes | yes |
| Resource write capability | yes | yes | no | yes | yes | no |
| Resource ACL manage | yes | yes | no | no | no | no |
| Integration manage | yes | yes | no | no | no | no |
| AI use | yes | yes | yes | yes | yes | no |
| Audit read | yes | yes | yes | no | no | no |

An admin may manage normal members, but only an owner may assign `owner` or `admin` roles. This prevents administrative privilege escalation through the membership endpoint.

## Restricted resource ACL

The role matrix is a capability ceiling, not permission to read every object. Restricted resources require a matching `resource_grants` row for the user, including owners and admins.

A `write` grant implies read access to the same resource. A `read` grant never implies write access. A grant cannot elevate a role beyond its capability ceiling; for example, a guest with a stored write grant still cannot write because the guest role lacks `resource.write`.

`resource_type` is a stable namespaced identifier such as `slack.channel`, `github.repository`, `project` or `document`. `resource_id` is the source/canonical identifier. Grant creation is allowed only for users who already belong to the same organisation.

## Slack privacy boundary

For the production MVP, Slack direct messages are not ingested. Public/shared channels still require workspace-admin authorisation, and private channels are opt-in. Source visibility must be retained and Brain ACL checks must run before retrieval.

## Audit hooks

Authorization denials emit structured `brain.security` events with organisation, actor, permission, reason and resource identifiers where relevant. Resource ACL create/delete operations emit structured security events. These hooks intentionally contain no access tokens, provider secrets or message/document contents.

Persistent immutable audit storage and retention are completed under S-09.02.01; this feature establishes the mandatory emission points.

## Migration and rollback

Migration `20260906_0003` adds `resource_grants` with tenant/resource indexes, a uniqueness constraint and foreign-key boundaries. Its downgrade removes only the ACL table and indexes. Rollback therefore removes explicit restricted-resource grants; production rollback must not be used while routes depend on those grants without first disabling the dependent release.
