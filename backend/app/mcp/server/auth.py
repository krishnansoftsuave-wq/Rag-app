"""FastMCP bearer-token validation for the DocuBrain OAuth server."""

from fastmcp.server.auth import AccessToken, TokenVerifier

from app.core.security import decode_access_token


class DocuBrainTokenVerifier(TokenVerifier):
    """Accept only unexpired JWTs issued by the application's OAuth endpoint."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_access_token(token)
            subject = payload.get("sub")
            if not subject:
                return None
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "docubrain-mcp-client"),
                subject=subject,
                scopes=payload.get("scope", "mcp:tools").split(),
                claims=payload,
            )
        except Exception:
            return None
