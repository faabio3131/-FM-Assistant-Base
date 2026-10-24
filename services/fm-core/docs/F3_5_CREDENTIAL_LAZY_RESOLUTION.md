# F3.5 credential-resolution regression

A provider's credential is resolved when that route is attempted, not when the
candidate set is constructed. A primary route with a valid credential must work
even if a lower-priority fallback has an invalid/unavailable credential.

A credential unavailable at the time of actual execution is classified as a
transient dependency failure, so existing same-scope fallback policy may run.
The consumer is never given the credential reference or raw secret in an API error.

Commercial core remains not deployment-approved. All F3 gates still apply.
