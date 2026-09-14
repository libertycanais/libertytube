# Configuracao do Supabase

## 1. Criar o projeto

Crie um projeto exclusivo para o LibertyTube no Supabase.

## 2. Executar o schema

Abra o SQL Editor e execute o arquivo `libertytube_schema.sql`.

## 3. Criar e liberar usuarios

Crie o usuario em Authentication > Users. O trigger cria o perfil com
`ativo = false`. Depois de confirmar a compra, libere o acesso:

```sql
update public.perfis_usuario
set ativo = true
where user_id = (
    select id from auth.users where email = 'cliente@email.com'
);
```

Para liberar o material VIP:

```sql
update public.perfis_usuario
set material_vip = true
where user_id = (
    select id from auth.users where email = 'cliente@email.com'
);
```

## 4. Configurar o aplicativo

Copie os valores do projeto para:

`%LOCALAPPDATA%\LibertyTube\backend.json`

Use somente a chave publica `anon`. A chave `service_role` nunca deve ser
embutida no aplicativo.

## 5. Publicar conteudo

Exemplo de aula:

```sql
insert into public.aulas
    (titulo, descricao, link_url, modulo, duracao, ordem, ativo)
values
    ('Bem-vindo ao LibertyTube', 'Conheca o fluxo completo do aplicativo',
     'https://seu-site/aula-1', 'Comecando', '5 min', 1, true);
```

Os links de suporte e comunidade ficam em `config_app`:

```sql
update public.config_app
set valor = 'https://wa.me/5500000000000'
where chave = 'whatsapp_suporte';

update public.config_app
set valor = 'https://chat.whatsapp.com/seu-grupo'
where chave = 'whatsapp_grupo';
```
