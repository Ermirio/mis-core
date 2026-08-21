# Backlog

Registro de melhorias futuras que surgiram durante operacao, restore ou suporte
em campo. Itens aqui ainda nao estao comprometidos com uma sprint especifica.

## Node-RED

### Forcar troca de senha no primeiro acesso

**Data:** 2026-07-31
**Origem:** restore de VM OT e recadastro de usuarios Node-RED.

Hoje o usuario Node-RED e cadastrado pelo admin Django em:

```text
MIS Core Admin -> Equipamentos -> Usuarios Node-RED
```

A senha inicial tambem e definida pelo admin. O usuario final nao possui uma
tela propria para trocar sua senha.

Melhoria desejada:

- Permitir marcar um `NodeRedUser` como "deve trocar senha no primeiro acesso".
- Ao autenticar com senha temporaria, redirecionar para uma tela de troca de
  senha antes de liberar o editor Node-RED.
- Exigir senha atual, nova senha e confirmacao.
- Gravar a nova senha usando `NodeRedUser.set_password()`.
- Remover a flag de troca obrigatoria apos sucesso.
- Manter o fluxo atual do admin Django como fallback para reset de senha.

Observacoes de implementacao:

- A fonte de verdade continua sendo `equipamentos.models.NodeRedUser`.
- Nao deve misturar senha do `auth.User` do Django com senha do Node-RED.
- A tela pode viver no gateway Django, antes do proxy para `/nodered/`.
- O comportamento atual deve permanecer: admin consegue criar, editar,
  desativar e resetar senha pelo Django Admin.
