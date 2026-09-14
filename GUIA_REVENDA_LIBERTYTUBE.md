# Guia de Revenda LibertyTube

## Envio para o cliente

1. Envie o arquivo `LibertyTube_1.0.0_Windows.zip`.
2. O cliente deve extrair o ZIP inteiro.
3. Dentro da pasta extraida, deve abrir `INSTALAR_LIBERTYTUBE.bat`.
4. Depois da instalacao, o atalho LibertyTube aparece na area de trabalho.
5. O cliente entra com o email e a senha fornecidos pela revenda.

Nao envie arquivos de sessao, senhas do Supabase ou a chave `service_role`.

## Liberar um cliente

Crie o usuario em Authentication > Users no Supabase e confirme o email.
Depois libere o perfil:

```sql
update public.perfis_usuario p
set ativo = true
from auth.users u
where p.user_id = u.id
  and u.email = 'cliente@email.com';
```

## Material VIP

```sql
update public.perfis_usuario p
set material_vip = true
from auth.users u
where p.user_id = u.id
  and u.email = 'cliente@email.com';
```

## Suporte

O instalador configura automaticamente o LibertyTube para usar o Supabase
do produto. O cliente nao precisa instalar Python, FFmpeg ou bibliotecas
manualmente.
