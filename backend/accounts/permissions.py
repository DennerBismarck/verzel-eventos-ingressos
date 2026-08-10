"""
Permissões por papel.

Como funciona no DRF: antes de executar a view, o framework chama
`has_permission(request, view)` de cada classe listada em `permission_classes`.
Se qualquer uma retornar False, a resposta é 403 e a view nem roda.

Por que checar o papel no BACKEND e não só esconder o botão no front:
o front é código do cliente — dá pra abrir o DevTools e chamar a API na mão.
A guarda de rota no Next.js é conveniência de UX; a autorização de verdade
mora aqui.
"""

from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    """Base: subclasse define `required_role`."""

    required_role: str | None = None

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            # is_active explícito, mesmo o simplejwt já recusando token de
            # usuário inativo na autenticação. Defesa em profundidade: esta
            # classe não deve assumir QUEM autenticou. Trocar o backend, somar
            # uma sessão de admin ou autenticar por outro meio não pode
            # reabrir a porta para uma conta desativada.
            and user.is_active
            and user.role == self.required_role
        )


class IsOrganizer(HasRole):
    message = "Apenas organizadores podem acessar este recurso."
    required_role = User.Role.ORGANIZER


class IsCustomer(HasRole):
    message = "Apenas clientes podem acessar este recurso."
    required_role = User.Role.CUSTOMER


class IsGate(HasRole):
    message = "Apenas usuários de portaria podem acessar este recurso."
    required_role = User.Role.GATE
