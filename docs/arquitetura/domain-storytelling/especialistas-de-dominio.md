# Especialistas de Domínio e Entrevistas — Oficina Mecânica

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

> Entrevistas simuladas geradas com assistência de IA (Claude) e revisadas pela equipe PytStop.
> Os especialistas de domínio são fictícios — representam papéis típicos de uma oficina
> mecânica de médio porte, baseados em pesquisa de mercado e experiência do setor.

---

## Mapeamento Entrevistas → Diagramas

| Entrevista | Especialista | Diagrama Domain Storytelling |
|---|---|---|
| 1 — Dono e Mecânico-Chefe | Seu Carlos | [oficina-recepcao-os.egn](oficina-recepcao-os.egn), [oficina-execucao-entrega.egn](oficina-execucao-entrega.egn) |
| 2 — Consultora Técnica / Recepcionista | Dona Marta | [oficina-recepcao-os.egn](oficina-recepcao-os.egn), [oficina-acompanhamento-cliente.egn](oficina-acompanhamento-cliente.egn) |
| 3 — Mecânico Especialista | Reginaldo | [oficina-diagnostico-orcamento.egn](oficina-diagnostico-orcamento.egn), [oficina-execucao-entrega.egn](oficina-execucao-entrega.egn) |
| 4 — Orçamentista e Comprador | Leandro | [oficina-diagnostico-orcamento.egn](oficina-diagnostico-orcamento.egn), [oficina-gestao-estoque.egn](oficina-gestao-estoque.egn) |
| 5 — Cliente Fiel | Fábio | [oficina-acompanhamento-cliente.egn](oficina-acompanhamento-cliente.egn) |

---

## Sumário

1. [Quem são os especialistas de domínio](#1-quem-são-os-especialistas-de-domínio)
2. [Contexto da oficina fictícia](#2-contexto-da-oficina-fictícia)
3. [Entrevista 1 — Seu Carlos (Dono e Mecânico-Chefe)](#3-entrevista-1--seu-carlos-dono-e-mecânico-chefe)
4. [Entrevista 2 — Dona Marta (Consultora Técnica / Recepcionista)](#4-entrevista-2--dona-marta-consultora-técnica--recepcionista)
5. [Entrevista 3 — Reginaldo (Mecânico Especialista)](#5-entrevista-3--reginaldo-mecânico-especialista)
6. [Entrevista 4 — Leandro (Orçamentista e Comprador de Peças)](#6-entrevista-4--leandro-orçamentista-e-comprador-de-peças)
7. [Entrevista 5 — Fábio (Cliente Fiel)](#7-entrevista-5--fábio-cliente-fiel)
8. [Termos de domínio descobertos](#8-termos-de-domínio-descobertos)
9. [Processos de negócio na perspectiva dos especialistas](#9-processos-de-negócio-na-perspectiva-dos-especialistas)
10. [Regras implícitas descobertas](#10-regras-implícitas-descobertas)
11. [Fontes e referências](#11-fontes-e-referências)

---

## 1. Quem são os especialistas de domínio

Cada papel na oficina carrega conhecimento tácito — regras nunca escritas, mas que governam o dia a dia.

### 1.1 Dono / Gerente da Oficina

- **O que faz**: supervisiona toda a operação, define preços, negocia com fornecedores estratégicos, resolve casos difíceis
- **Relevância**: detém a visão completa do fluxo de ponta a ponta e as regras de negócio não escritas (ex: quando dar desconto, quando recusar um serviço, quando fazer exceções)
- **Conhecimento exclusivo**: as margens reais de cada tipo de serviço, o histórico de confiança de cada fornecedor, os limites de negociação com cada cliente

### 1.2 Consultor Técnico / Recepcionista

- **O que faz**: recebe o cliente, abre a Ordem de Serviço, traduz a queixa do cliente para linguagem técnica, comunica orçamentos, faz follow-up
- **Por que importa**: é a interface entre o mundo do cliente (leigo) e o mundo da oficina (técnico). Toda informação passa por essa pessoa
- **Conhecimento exclusivo**: o perfil de cada cliente, quem aceita orçamento rápido, quem precisa de explicação detalhada, quem sempre pechincha

### 1.3 Mecânico Especialista

- **O que faz**: executa diagnósticos complexos, realiza os reparos, testa o veículo após o serviço
- **Relevância**: detém o conhecimento técnico profundo — sabe interpretar sintomas, identificar causas raiz, estimar tempo de reparo com precisão. Conhece os padrões de falha por modelo, quais peças paralelas são confiáveis, qual a "personalidade" de cada tipo de barulho

### 1.4 Orçamentista / Comprador de Peças

- Monta orçamentos, consulta fornecedores, controla o estoque de peças
- Conecta o diagnóstico técnico ao custo financeiro — sabe onde comprar cada peça, prazos de entrega, alternativas (original vs. paralela vs. desmanche)
- **Conhecimento exclusivo**: preços reais de mercado, quais fornecedores entregam rápido, margem de cada peça

### 1.5 Cliente

- Traz o veículo, descreve o problema, aprova (ou rejeita) orçamentos, retira o veículo
- Suas frustrações revelam problemas no fluxo que os profissionais da oficina já naturalizaram: dores de comunicação, expectativas de transparência, o que faz voltar ou ir embora

---

## 2. Contexto da oficina fictícia

**Auto Mecânica São Carlos** — oficina de médio porte localizada em bairro misto (residencial e comercial) de cidade de ~200 mil habitantes no interior de São Paulo.

- **Fundação**: 1998 (28 anos)
- **Proprietário**: Carlos Henrique dos Santos ("Seu Carlos"), 58 anos, mecânico desde os 16
- **Equipe**: 6 funcionários (2 mecânicos especialistas, 1 mecânico geral, 1 aprendiz, 1 recepcionista/consultora, 1 orçamentista/comprador)
- **Estrutura**: 3 elevadores, 1 área de recepção, 1 almoxarifado, 1 área de lavagem
- **Capacidade**: ~15 veículos simultâneos, ~8 OS finalizadas por dia
- **Faturamento**: R$ 120-150 mil/mês
- **Foco**: veículos nacionais e populares importados (até 15 anos)
- **Informatização atual**: zero. Tudo em papel, cadernos e WhatsApp

---

## 3. Entrevista 1 — Seu Carlos (Dono e Mecânico-Chefe)

**Data simulada**: 11/03/2026
**Duração**: 1h30
**Local**: Escritório da oficina (mesa cheia de papéis, calendário de parede, quadro de OSs na parede)
**Entrevistador**: Dev (desenvolvedor do sistema)
**Especialista**: Carlos Henrique dos Santos, 58 anos, dono e mecânico-chefe

---

**Dev**: Seu Carlos, me conta como funciona o dia a dia da oficina, desde que o cliente chega.

**Seu Carlos**: *recosta na cadeira* Olha, o cliente chega, fala com a Dona Marta na recepção. Ela anota tudo: nome, telefone, placa do carro, quilometragem, e o que o cliente ta reclamando. Depois ela me chama e a gente decide o que fazer. Se é coisa simples, eu já sei o que é só de ouvir. Se não, a gente precisa fazer um diagnóstico mais detalhado.

**Dev**: E como é esse diagnóstico?

**Seu Carlos**: Depende. Se é barulho, eu preciso ouvir o carro. Se é problema mecânico visível, eu ponho no elevador e olho por baixo. Se é eletrônico, a gente usa o scanner. Mas na maioria das vezes, eu já sei o que é. Trinta anos fazendo isso, né? *ri*

**Dev**: Depois do diagnóstico, o que acontece?

**Seu Carlos**: Eu passo pro Leandro montar o orçamento. Ele cota as peças, eu defino a mão de obra, e a Dona Marta passa pro cliente. Se o cliente aprovar, a gente começa. Se não aprovar... *dá de ombros* O carro fica aqui esperando.

**Dev**: E se o carro ficar muito tempo esperando?

**Seu Carlos**: *coça a cabeça* Ai é problema. Tem carro aqui que o dono sumiu. Mandou arrumar, a gente fez o orçamento, o cara não respondeu e nunca mais apareceu. Eu ligo, mando mensagem, nada. Ai o carro fica ocupando espaço. Depois de uns trinta dias eu penso em cobrar estadia, mas na prática nunca cobrei de ninguém. É uma dor de cabeça.

**Dev**: Quando o orçamento é aprovado e o serviço começa, como vocês controlam o andamento?

**Seu Carlos**: *aponta pro quadro na parede* Tá vendo aquele quadro? Ali tem as colunas: "Aguardando Serviço", "Em Diagnóstico", "Aguardando Peça", "Em Serviço", "Pronto". Cada OS é um papelzinho. A gente move conforme o carro vai andando.

**Dev**: E se aparece um serviço adicional durante o reparo?

**Seu Carlos**: Ah, isso acontece toda hora. O cara traz pra trocar o freio e quando abre, descobre que o flexível tá rachado. Aí depende do valor. Se é coisa pequena, eu autorizo o mecânico a fazer e depois a gente avisa o cliente. Se é coisa grande, para tudo, faz novo orçamento.

**Dev**: Qual o limite entre "coisa pequena" e "coisa grande"?

**Seu Carlos**: *pensa* Não tem regra escrita, mas... se o adicional passa de uns quinze por cento do orçamento original, eu prefiro ligar pro cliente. Agora, se é R$ 50 numa mangueira, eu mando trocar e acrescento na nota. O bom senso manda.

**Dev**: E quando o serviço termina?

**Seu Carlos**: O mecânico faz o teste. Liga o carro, dá uma volta no quarteirão, verifica se tá tudo OK. Depois a Dona Marta liga pro cliente vir buscar. O cliente vem, a gente explica o que foi feito, cobra, e entrega o carro.

**Dev**: Como é a cobrança?

**Seu Carlos**: *conta nos dedos* Dinheiro, Pix, cartão de débito ou crédito. Crédito a gente parcela em até três vezes sem juros. Acima de três, passa a taxa da maquininha. E tem os clientes antigos que pagam "no caderninho"... *ri* Mas isso tá diminuindo, hoje a maioria paga na hora.

**Dev**: Seu Carlos, se eu fosse resumir: qual é o maior problema que o sistema precisa resolver?

**Seu Carlos**: *sem hesitar* Saber onde cada carro está. Hoje eu olho pro quadro e sei mais ou menos... mas às vezes o papelzinho cai, alguém esquece de mover, e eu não sei se o carro tá aguardando peça ou já tá em serviço. E o cliente liga perguntando e eu tenho que ir lá olhar. Isso me tira do que eu sei fazer: consertar carro.

---

## 4. Entrevista 2 — Dona Marta (Consultora Técnica / Recepcionista)

**Data simulada**: 11/03/2026
**Duração**: 1h
**Local**: Balcão da recepção, entre atendimentos
**Entrevistador**: Dev (desenvolvedor do sistema)
**Especialista**: Marta de Souza Lima, 47 anos, trabalha na oficina há 12 anos

---

**Dev**: Dona Marta, como começa o atendimento quando o cliente chega?

**Dona Marta**: *organizando papéis* Primeiro eu pergunto se já é cliente nosso. Se é, eu puxo a ficha dele — tenho um fichário aqui, alfabético. Se é novo, eu faço o cadastro: nome completo, CPF, endereço, telefone, e-mail. Depois anoto os dados do carro: placa, modelo, ano, cor, quilometragem.

**Dev**: E a reclamação do cliente?

**Dona Marta**: Eu anoto do jeitinho que ele fala. Se ele diz "o carro tá fazendo tec-tec quando viro o volante", eu escrevo exatamente isso. Depois o mecânico traduz pra linguagem técnica, mas a queixa original fica registrada.

**Dev**: Existe agendamento?

**Dona Marta**: Existe, mas é informal. O cliente liga ou manda WhatsApp e eu falo "pode trazer segunda de manhã". Mas não tem horário certo, não. É mais um "dia combinado". Agora, revisão programada eu agendo direitinho, porque aí eu sei o que vai ser feito e quanto tempo leva.

**Dev**: Qual a diferença entre uma revisão programada e um reparo?

**Dona Marta**: *conta nos dedos* A revisão é quando o carro não tem problema. O cliente traz pra fazer a manutenção preventiva — troca de óleo, filtros, verificar freio, suspensão, correia. Eu já sei o que vai ser feito, já sei o preço, já sei o tempo. O orçamento é quase automático.

Agora, reparo é quando tem problema. "O carro tá fazendo barulho", "Tá vazando óleo", "Não pega". Aí eu não sei o que é até o mecânico olhar. Precisa de diagnóstico primeiro.

**Dev**: Então são dois fluxos diferentes?

**Dona Marta**: São! Na revisão, eu já posso dar o orçamento ali na hora, o cliente aprova, e o carro já entra. No reparo, primeiro precisa do diagnóstico, depois do orçamento, depois da aprovação. É bem mais demorado.

**Dev**: Quando o cliente chega pra um reparo, o que você anota?

**Dona Marta**: Eu anoto o nome, telefone — agora é tudo WhatsApp, né? — placa do carro, modelo, ano, e a quilometragem. E a **reclamação do cliente**. Eu escrevo exatamente o que ele fala. Às vezes o cliente fala coisas engraçadas: "o carro tá gemendo", "tá com mau hálito"... *ri* Mas eu anoto do jeito que ele fala, porque é importante pro mecânico entender o sintoma.

**Dev**: Você disse "reclamação do cliente". O Seu Carlos chamou de "queixa do cliente". É a mesma coisa?

**Dona Marta**: *pensa* É... pra gente aqui, é a mesma coisa. Uns falam queixa, outros falam reclamação, outros falam sintoma. Mas é tudo a mesma coisa: o que o cliente tá sentindo no carro.

**Dev**: Bom saber. Depois que você abre a OS, o que acontece?

**Dona Marta**: Eu coloco a OS no quadro, na coluna "Aguardando Serviço". Aí o Carlos ou o chefe de oficina — que na verdade é o próprio Carlos, *ri* — pega e distribui pros mecânicos.

**Dev**: E o orçamento? Como funciona?

**Dona Marta**: Depois que o mecânico faz o diagnóstico, ele vem e me fala o que precisa. "Precisa trocar as duas pastilhas e os dois discos de freio". Aí eu passo pro Leandro, que cota as peças, calcula o preço, e me dá o orçamento montado. Aí eu ligo pro cliente.

**Dev**: Como você passa o orçamento pro cliente?

**Dona Marta**: Antigamente era tudo por telefone. Hoje é noventa por cento WhatsApp. Eu mando o orçamento escrito, às vezes com foto do que tá estragado — o Reginaldo tira foto do celular dele e me manda. O cliente vê, pergunta, negocia preço — *suspira* — e aí aprova ou não.

**Dev**: Negociação de preço acontece muito?

**Dona Marta**: *olha pro lado* Acontece. O cliente fala "tá caro", aí eu tenho que ver com o Carlos se pode dar desconto. Geralmente a gente tem uns dez, quinze por cento de margem pra negociar na mão de obra. Nas peças não tem muito como mexer, a não ser que o cliente aceite peça paralela em vez de original.

**Dev**: Peça paralela vs. original — como funciona essa decisão?

**Dona Marta**: A gente sempre orçamenta com peça original. Se o cliente achar caro, a gente oferece a paralela. Mas tem que explicar a diferença. Peça original tem garantia do fabricante, paralela tem garantia da loja só. E tem peça paralela boa e peça paralela ruim. O Carlos sabe quais marcas são confiáveis.

**Dev**: E garantia do serviço?

**Dona Marta**: A gente dá noventa dias de garantia no serviço e na peça. Se der problema nesse prazo, a gente refaz sem cobrar. Mas só se for o mesmo problema, né? Se o cliente trocar a pastilha de freio e três meses depois o motor fundir, não tem nada a ver.

**Dev**: Dona Marta, qual a sua maior dificuldade no dia a dia?

**Dona Marta**: *sem pensar* Achar informação. O cliente liga e pergunta "como tá meu carro?" e eu tenho que largar tudo, ir lá no quadro, procurar a OS, às vezes a OS não tá no quadro porque alguém tirou e não devolveu, aí eu tenho que perguntar pro mecânico. Perde dez, quinze minutos só pra responder uma pergunta simples.

Outra coisa: histórico do cliente. Quando o cara volta e fala "eu troquei a embreagem aqui ano passado", eu tenho que ir lá no arquivo físico procurar a OS antiga. Às vezes acho, às vezes não acho. É uma vergonha.

**Dev**: E se o cliente pede um orçamento e não responde?

**Dona Marta**: Eu tenho um caderninho com os orçamentos pendentes. *mostra o caderno* Olha: "José, Gol prata, orçamento R$ 1.200, aguardando desde 05/03". Eu ligo uma vez, mando mensagem, e se em uma semana não responder, eu marco aqui "não respondeu" e aviso o Carlos pra decidir o que faz com o carro.

**Dev**: E pagamento? Como funciona?

**Dona Marta**: O cliente pode pagar em dinheiro, Pix, cartão de débito ou crédito. Crédito a gente parcela em até três vezes sem juros. Acima de três, a gente acrescenta a taxa da maquininha. Mas tudo isso é na conversa, não tem regra fixa. Depende do valor, depende do cliente. Cliente antigo às vezes a gente parcela no fiado mesmo, no caderninho.

**Dev**: Fiado? Existe um controle disso?

**Dona Marta**: *mostra outro caderno* Esse aqui é o caderno dos "pendurados". Quem tá devendo, quanto, desde quando. Tem gente aqui que deve desde 2024. Mas é pouca gente, a maioria paga direitinho.

---

## 5. Entrevista 3 — Reginaldo (Mecânico Especialista)

**Data simulada**: 12/03/2026
**Duração**: 1h
**Local**: Ao lado do elevador 3, durante um intervalo entre serviços
**Entrevistador**: Dev (desenvolvedor do sistema)
**Especialista**: Reginaldo Aparecido Gomes, 42 anos, mecânico há 25 anos, 12 na oficina do Seu Carlos

---

**Dev**: Reginaldo, me conta como você recebe um serviço.

**Reginaldo**: *limpando as mãos com estopa* O Carlos me chama, me dá a OS e fala "olha isso aqui". Eu leio a queixa do cliente, ligo o carro, escuto, dou uma volta no quarteirão às vezes, e aí já tenho uma ideia do que pode ser. Aí eu ponho no elevador e começo a investigar.

**Dev**: Esse processo de investigação, como funciona? Você segue algum roteiro?

**Reginaldo**: *ri* Roteiro não, mas tem uma lógica. Primeiro eu confirmo o sintoma que o cliente descreveu. Aí eu vou eliminando. Se tá fazendo barulho na frente, eu verifico suspensão, direção, freio. Se é na traseira, verifico amortecedor, mola, rolamento. Cada barulho tem uma "personalidade" — barulho de metal contra metal é diferente de barulho de borracha, que é diferente de barulho de coisa solta.

**Dev**: Você disse "personalidade do barulho". Isso é experiência pura ou tem algo mais técnico?

**Reginaldo**: É experiência. *bate no peito* Vinte e cinco anos ouvindo carro. Mas tem coisas que eu uso também: scanner automotivo pra ler os códigos de erro do computador do carro, manômetro pra medir pressão, multímetro pra parte elétrica. Carro moderno sem scanner você não faz nada.

**Dev**: Quando você termina o diagnóstico, o que você faz?

**Reginaldo**: Eu falo pra Marta ou pro Carlos o que achei. "Precisa trocar tal peça, a causa é tal". Aí passo a lista do que precisa. Às vezes eu tiro foto do celular e mando no grupo do WhatsApp da oficina.

**Dev**: Existe um grupo de WhatsApp da oficina?

**Reginaldo**: *ri* Tem sim. "Oficina do Carlão". A gente manda foto de peça estragada, avisa quando terminou serviço, essas coisas. Não é organizado, mas funciona.

**Dev**: Depois que o orçamento é aprovado, como é a execução?

**Reginaldo**: Aí depende se tem peça. Se tem peça em estoque, eu já começo. Se não tem, eu tenho que esperar chegar. Às vezes demora um dia, às vezes demora uma semana. Peça importada então... *faz gesto de demora* Aí o carro fica no elevador, parado.

**Dev**: E se você precisa do elevador pra outro carro?

**Reginaldo**: Aí eu tiro o carro desmontado do elevador, ponho no chão num canto, marco as peças tudo direitinho pra não perder, e libero o elevador. Isso é ruim, porque aumenta o risco de perder peça e aumenta o tempo de serviço.

**Dev**: Você mencionou "serviços adicionais". Me conta mais.

**Reginaldo**: É o dia a dia. Você abre pra trocar a junta do cabeçote e descobre que o bloco tá com problema. Você vai trocar o disco de freio e vê que a pinça tá travada. Sempre aparece coisa. Aí eu falo pro Carlos: "olha, apareceu mais isso aqui". E ele decide se liga pro cliente ou se faz e acrescenta na conta.

**Dev**: Como você registra esses serviços adicionais?

**Reginaldo**: *coça a cabeça* Aí que é o problema. Às vezes eu falo pro Carlos e ele anota. Às vezes eu anoto num papel avulso e grampeia na OS. Às vezes eu só falo e ninguém anota. Aí na hora de fechar a conta falta informação. Já aconteceu do cliente perguntar "mas por que tá mais caro do que o orçamento?" e a gente não ter registro do que foi aprovado a mais. É ruim.

**Dev**: Quando você termina o serviço, o que acontece?

**Reginaldo**: Eu faço o teste. Ligo o carro, dou uma volta, verifico se tá tudo certo. Se tiver OK, eu aviso a Marta que o carro tá pronto. Ela liga pro cliente vir buscar.

**Dev**: Existe um checklist de teste final?

**Reginaldo**: *nega com a cabeça* Não, é no feeling. Eu sei o que eu mexi, eu sei o que precisa testar. Se eu troquei o freio, eu testo o freio. Se eu troquei a suspensão, eu testo a suspensão. Mas formalizado, com checklist, não tem.

**Dev**: Uma coisa que me chamou atenção: você disse que cada mecânico tem uma especialidade. E se aparece um serviço que não é da sua área?

**Reginaldo**: Olha, eu faço praticamente tudo. Mas se é algo muito específico de ar-condicionado automotivo, por exemplo, o Carlos chama um cara de fora. A gente tem uns parceiros que fazem serviços específicos. Ar-condicionado, vidro elétrico, som automotivo — isso a gente terceiriza.

**Dev**: Então existem serviços que a oficina não faz internamente?

**Reginaldo**: Existem. E a gente funciona como intermediário: o carro fica aqui, a gente chama o especialista, ele vem aqui e faz, e a gente cobra do cliente. Aí na OS aparece o serviço terceirizado junto com os nossos.

**Dev**: Última pergunta: se você pudesse mudar uma coisa na oficina, o que seria?

**Reginaldo**: *pensa* Eu queria saber o histórico do carro. Quando chega um carro que já veio aqui antes, eu queria saber o que já foi feito. Porque às vezes o cara troca um amortecedor e volta seis meses depois reclamando do mesmo barulho. Se eu tiver o histórico, eu sei que o amortecedor já foi trocado e o problema é em outro lugar. Sem histórico, eu começo do zero toda vez.

---

## 6. Entrevista 4 — Leandro (Orçamentista e Comprador de Peças)

**Data simulada**: 12/03/2026
**Duração**: 40min
**Local**: Mesa do Leandro (computador com várias abas de fornecedores abertas)
**Entrevistador**: Dev (desenvolvedor do sistema)
**Especialista**: Leandro Santos de Oliveira, 31 anos, trabalha na oficina há 4 anos

---

**Dev**: Leandro, me explica como você monta um orçamento.

**Leandro**: Beleza. O mecânico faz o diagnóstico e me passa a lista do que precisa. Tipo: "Gol 2018, precisa de duas pastilhas dianteiras, dois discos dianteiros, e fluido de freio". Aí eu vou nos meus fornecedores e coto.

**Dev**: Quantos fornecedores você consulta?

**Leandro**: Pra peça comum, uns três ou quatro. Eu tenho os contatos no WhatsApp, mando a lista e eles mandam o preço. Pra peça mais rara, aí eu consulto mais gente, às vezes ligo pra desmanche também.

**Dev**: Desmanche?

**Leandro**: *explica* Desmanche é loja de peças usadas. Quando o serviço sai muito caro com peça nova, a gente oferece pro cliente a opção de peça de desmanche. Tem peças que vêm em ótimo estado. Motor, câmbio, alternador — às vezes comprar de desmanche é metade do preço. Mas aí a garantia é menor.

**Dev**: Interessante. Então no orçamento você pode ter mais de uma opção?

**Leandro**: Sim! Eu monto orçamento com peça original, com paralela, e às vezes com desmanche. O cliente escolhe. Aí a Marta passa as opções e o cliente decide.

**Dev**: Como você calcula a mão de obra?

**Leandro**: O Carlos tem a tabela na cabeça dele. Eu pergunto "Carlos, quanto é a mão de obra pra trocar freio do Gol?" e ele fala "duas horas". Aí eu multiplico pelo valor da hora da oficina, que hoje é cento e vinte reais. Mas isso muda dependendo do serviço. Serviço de motor a hora é mais cara, cento e cinquenta.

**Dev**: Então existem categorias de mão de obra com preços diferentes?

**Leandro**: *pensa* Nunca pensei assim, mas... é, acho que sim. Tem a mão de obra "normal", que é o grosso dos serviços. E a mão de obra "especializada", que é motor, câmbio, injeção eletrônica. Aí o Carlos cobra mais.

**Dev**: E o tempo de entrega das peças? Como funciona?

**Leandro**: Peça de giro alto — pastilha, filtro, correia — os fornecedores aqui da região entregam no mesmo dia, às vezes em duas horas. Peça mais específica pode demorar um, dois dias. Peça importada é o terror: uma semana, duas semanas. Já esperei peça de import trinta dias.

**Dev**: E como você controla o que já foi pedido, o que chegou?

**Leandro**: *mostra a tela* Eu tenho uma planilha no Excel. Uma aba por mês. Cada linha é um pedido: data, fornecedor, peça, quantidade, preço, OS relacionada, se já chegou ou não. É manual, eu que preencho. Às vezes eu esqueço de marcar que chegou e aí fico ligando pro fornecedor perguntando de uma peça que já tá aqui.

**Dev**: Quando a peça chega, o que acontece?

**Leandro**: Eu confiro, guardo na prateleira do carro correspondente — a gente separa por OS, pra não misturar — e aviso o mecânico que pode começar. Aí a OS sai de "Aguardando Peça" e vai pra "Em Serviço".

**Dev**: E se o fornecedor manda a peça errada?

**Leandro**: *suspira* Acontece mais do que devia. Aí eu tenho que devolver, pedir de novo, e o carro fica parado mais tempo. O cliente fica bravo e a culpa cai em mim, mas não é minha culpa, é do fornecedor. Por isso eu sempre confiro o número da peça antes de aceitar a entrega.

**Dev**: Número da peça?

**Leandro**: Toda peça tem um código único do fabricante. Tipo, uma pastilha de freio dianteira do Gol G5 tem o código tal. Se o fornecedor manda uma pastilha com código diferente, não serve. Eu tenho catálogos online pra consultar o código certo de cada peça pra cada modelo de carro.

---

## 7. Entrevista 5 — Fábio (Cliente Fiel)

**Data simulada**: 13/03/2026
**Duração**: 25min
**Local**: Área de espera da oficina
**Entrevistador**: Dev (desenvolvedor do sistema)
**Especialista**: Fábio Rocha de Almeida, 39 anos, engenheiro civil, cliente da oficina há 7 anos

---

**Dev**: Fábio, como cliente, me conta sua experiência com a oficina.

**Fábio**: Eu trago meus dois carros aqui — o meu e o da minha esposa. Conheci a oficina por indicação de um amigo e nunca mais saí.

**Dev**: O que te faz voltar?

**Fábio**: Confiança. Eu sei que o Seu Carlos não vai inventar serviço. Se ele falar que precisa trocar, precisa. E o preço é justo, não é o mais barato, mas também não é absurdo.

**Dev**: Como é o processo quando você traz o carro?

**Fábio**: Eu geralmente mando WhatsApp pra Dona Marta antes. Falo o que tá acontecendo e pergunto quando posso levar. Ela me dá um dia. Aí eu levo de manhã, deixo a chave com ela, e vou de Uber pro trabalho.

**Dev**: E o orçamento?

**Fábio**: Aí que demora um pouco. Às vezes no mesmo dia ela me manda o orçamento, às vezes só no dia seguinte. Depende da fila. Aí eu recebo no WhatsApp, vejo o valor, e aprovo. Quando é muito caro eu ligo pra entender melhor antes de aprovar.

**Dev**: O que te incomoda no processo?

**Fábio**: *pensa* A comunicação. Às vezes eu aprovo o orçamento e fico três dias sem saber de nada. Aí eu mando mensagem perguntando e a Dona Marta me fala que tá esperando peça. Mas ninguém me avisou que ia demorar! Eu preferia saber na hora: "olha, a peça vai chegar quinta, o carro fica pronto sexta".

**Dev**: Você gostaria de acompanhar o status do serviço?

**Fábio**: Com certeza! Tipo rastreamento de entrega, sabe? "Seu carro está em diagnóstico", "Aguardando aprovação", "Em serviço", "Pronto para retirada". Seria fantástico.

**Dev**: E o histórico de serviços?

**Fábio**: Eu guardo as OS em papel numa pasta. Mas já perdi várias. Se tivesse um histórico digital, que eu pudesse ver pelo celular, seria perfeito. "Em março de 2025 você trocou o óleo. Em agosto trocou a correia." Aí eu sei quando precisa trocar de novo.

**Dev**: Você já teve algum problema com a oficina?

**Fábio**: Uma vez só. Troquei um amortecedor e em dois meses voltou a fazer barulho. Trouxe de volta, o Reginaldo olhou e viu que era a peça que veio com defeito. Trocaram sem cobrar. Aí que eu digo: confiança. Outro lugar ia falar que não era garantia, mas aqui não, resolveram.

**Dev**: Se você pudesse melhorar uma coisa, o que seria?

**Fábio**: Queria agendar online. Escolher o dia, escolher o horário, e pronto. E quando o carro tiver pronto, receber uma notificação automática. Não precisa de nada sofisticado, só me avisa. "Seu carro tá pronto, pode buscar."

---

## 8. Termos de domínio descobertos

Termos que surgiram nas entrevistas e que compõem a **Linguagem Ubíqua** do projeto:

### 8.1 Entidades e Agregados

| Termo do Domínio | Contexto | Sinônimos Encontrados |
|---|---|---|
| Ordem de Serviço (OS) | Documento central que registra tudo sobre o serviço | - |
| Orçamento | Proposta de preço enviada ao cliente para aprovação | "cotação" (informal) |
| Diagnóstico | Avaliação técnica feita pelo mecânico | "investigação", "análise" |
| Queixa do Cliente | Descrição do problema nas palavras do cliente | "reclamação", "sintoma" |
| Veículo | Carro do cliente, identificado por placa, modelo, ano | "carro" |
| Cliente | Pessoa que traz o veículo | "dono do carro", "proprietário" |
| Peça | Componente necessário para o reparo | "material" |
| Serviço | Trabalho realizado pelo mecânico | "reparo", "manutenção" |
| Serviço Adicional | Problema descoberto durante a execução | "adicional", "achado" |

### 8.2 Objetos de Valor

| Termo | Descrição |
|---|---|
| Mão de Obra | Valor cobrado pelo trabalho, calculado por horas-padrão |
| Margem sobre Peça | Percentual adicionado ao custo da peça (40-50%) |
| Hora da Oficina | Valor/hora do trabalho (R$ 120 normal, R$ 150 especializada) |
| Tempo Padrão | Tempo tabelado para cada serviço por modelo de carro |
| Garantia do Serviço | Período de cobertura (90 dias padrão) |

### 8.3 Etapas do Fluxo (Estados da OS)

> Os especialistas descreveram 11 estados nas entrevistas. O sistema implementa 8 (7 base + AguardandoAprovacaoComplementar via RF-016) — os demais foram combinados ou absorvidos em transições internas. Ver [Glossário (`StatusOrdem`)](../../requisitos/glossario.md) e [ADR-007](../adr/007-organizacao-contextos-delimitados.md).

1. **Aguardando Serviço** — OS aberta, veículo na fila
2. **Em Diagnóstico** — mecânico investigando o problema
3. **Aguardando Orçamento** — diagnóstico feito, orçamento sendo montado
4. **Aguardando Aprovação** — orçamento enviado ao cliente
5. **Aprovado** — cliente autorizou o serviço
6. **Aguardando Peça** — peça foi pedida, esperando entrega
7. **Em Serviço** — mecânico executando o reparo
8. **Em Teste** — serviço feito, mecânico testando
9. **Aguardando Entrega** — pronto, esperando cliente buscar
10. **Entregue** — cliente retirou o veículo
11. **Cancelado** — serviço cancelado (cliente desistiu, carro abandonado)

### 8.4 Papéis

| Papel | Pessoa(s) na Oficina |
|---|---|
| Dono / Gerente | Seu Carlos |
| Consultor Técnico / Recepcionista | Dona Marta |
| Mecânico Especialista | Reginaldo |
| Mecânico Geral | Tiago |
| Mecânico Aprendiz | Júnior |
| Orçamentista / Comprador | Leandro |
| Auxiliar de Mecânico | (não entrevistado) |
| Lavador | (não entrevistado) |
| Cliente | Fábio (entrevistado) |

### 8.5 Jargão do Domínio

| Jargão | Significado |
|---|---|
| "Cabeludo" | Serviço complexo, de alta dificuldade |
| "Giro rápido" | Peça que tem alta rotatividade no estoque |
| "Sob demanda" | Peça comprada apenas quando necessária |
| "Desmanche" | Loja de peças usadas / recicladas |
| "Paralela" | Peça não-original de fabricante alternativo |
| "Original" | Peça do fabricante do veículo (OEM) |
| "Pendurado" | Cliente que tá devendo |
| "Fiado" | Venda a prazo informal, sem cartão |
| "Carbonado" | Bloco de OS com cópia em carbono |
| "Scanner" | Equipamento de diagnóstico eletrônico |
| "Código de erro" | Código que o computador do carro gera para indicar falha |
| "Retífica" | Oficina especializada em restaurar peças de motor |
| "Remanufaturada" | Peça usada com todas as partes defeituosas substituídas pelo fabricante; garantia de fábrica |
| "Recondicionada" | Peça usada com pequenos ajustes/reparos; sem garantia de fábrica |
| "Giro alto" / "Curva A" | Peça com alta rotatividade no estoque (filtros, óleos, pastilhas) |
| "Estoque mínimo" | Quantidade abaixo da qual é preciso fazer novo pedido ao fornecedor |
| "Pinça travada" | Componente do freio emperrado |

---

## 9. Processos de negócio na perspectiva dos especialistas

### 9.1 Processo: Atendimento e Abertura de OS

```
Cliente chega -> Dona Marta recebe -> Coleta dados (nome, telefone,
placa, km, queixa) -> Abre OS (bloquinho carbonado) -> Entrega via
ao cliente -> Coloca OS no quadro (coluna "Aguardando Serviço")
```

**Variante — Agendamento**: cliente manda WhatsApp antes. Marta combina dia. Dados já parcialmente coletados por mensagem.

**Variante — Revisão programada**: orçamento já é conhecido. Pode pular direto para "Aprovado" se cliente concordar.

### 9.2 Processo: Diagnóstico

```
Carlos distribui OS ao mecânico (por nível de complexidade) ->
Mecânico lê a queixa -> Confirma o sintoma (liga o carro, dirige,
escuta) -> Investiga causa (elevador, scanner, ferramentas) ->
Identifica o problema -> Comunica diagnóstico (verbal + foto
WhatsApp) -> Lista peças e serviços necessários
```

**Regra**: mecânico aprendiz não pega serviço de motor ou câmbio.

**Regra**: serviço de ar-condicionado, vidro elétrico, som = terceirizado.

### 9.3 Processo: Orçamento e Aprovação

```
Leandro recebe lista de peças -> Consulta 3-4 fornecedores (WhatsApp)
-> Monta orçamento (peça original + paralela + desmanche quando
aplicável) -> Carlos define mão de obra (tabela mental, por modelo e
serviço) -> Marta envia orçamento ao cliente (WhatsApp) -> Cliente
aprova, rejeita ou negocia
```

**Regra de negociação**: margem de 10-15% na mão de obra. Peças sem margem, mas pode oferecer paralela.

**Regra de timeout**: se cliente não responde em 1 semana, Marta cobra. Se não responde em ~1 mês, Carlos ameaça cobrar estadia (mas nunca cobra).

### 9.4 Processo: Execução do Serviço

```
Peça em estoque? -> Sim: mecânico começa imediatamente
                 -> Não: Leandro faz pedido -> Aguarda entrega
                     -> Confere peça recebida (código) -> Avisa mecânico

Mecânico executa serviço -> Descobre problema adicional?
  -> Não: continua até finalizar
  -> Sim: avalia gravidade:
      -> Até ~15% do orçamento original: faz e avisa depois
      -> Acima de 15%: para, comunica Carlos, novo orçamento parcial
      -> Acima de R$ 2.000: autorização por escrito/WhatsApp obrigatória
```

**Regra de autonomia**: limite informal para serviços adicionais depende do valor e da relação com o cliente (cliente antigo = mais autonomia).

### 9.5 Processo: Teste e Entrega

```
Mecânico termina serviço -> Faz teste (liga, dirige, verifica) ->
Se OK: avisa Marta -> Marta liga/manda WhatsApp pro cliente ->
Cliente vem buscar -> Marta faz o fechamento da OS -> Cobrança
(dinheiro, Pix, débito, crédito até 3x, ou "fiado") -> Entrega chave
-> Arquiva OS
```

**Variante**: se teste detecta problema, volta para execução.

### 9.6 Processo: Gestão de Estoque (simplificada)

```
Carlos verifica prateleira visualmente -> Se "tá no último": anota
pra pedir -> Leandro faz pedido de reposição -> Peça chega ->
Leandro confere e guarda

Critério de estoque: peça usada 3+ vezes por semana OU peça com
lead time longo de fornecedor
```

### 9.7 Processo: Garantia

```
Cliente volta reclamando do mesmo problema dentro de 90 dias ->
Marta localiza OS original (arquivo físico) -> Mecânico reavalia ->
Se defeito na peça: troca sem custo -> Se defeito no serviço: refaz
sem custo -> Se problema diferente: abre nova OS (serviço cobrado)
```

O prazo de 90 dias citado por Dona Marta corresponde à garantia legal do CDC (Art. 26, II) para serviços duráveis. A garantia deve constar por escrito na nota fiscal ou termo de garantia — cláusulas como "não damos garantia" são nulas.

---

## 10. Regras implícitas descobertas

Regras não formalizadas, descobertas durante as entrevistas:

### 10.1 Regras de Negócio

1. **Alocação por competência**: mecânicos recebem serviços de acordo com seu nível de experiência. Aprendiz não pega serviço cabeludo. Especialista não desperdiçado em serviço simples.

2. **Limite de autonomia para adicionais**: até ~15% do orçamento original, o mecânico pode executar sem nova aprovação. Acima disso, precisa de aprovação. Acima de R$ 2.000, aprovação por escrito.

3. **Regra do cliente antigo**: clientes com relacionamento longo têm mais flexibilidade — parcelamento no fiado, execução de adicionais sem aprovação prévia, prazos mais generosos.

4. **Orçamento triplo**: sempre que possível, apresentar opções com peça original, paralela e desmanche. Cliente decide.

5. **Garantia de 90 dias**: cobre o mesmo serviço e a mesma peça. Problema diferente = nova OS.

6. **Margem sobre peças**: 40-50% sobre o custo de compra.

7. **Mão de obra por tempo padrão**: cobra-se pelo tempo tabelado, não pelo tempo real. Se o mecânico é rápido, a oficina ganha mais. Se é lento, a oficina absorve.

8. **Duas categorias de mão de obra**: normal (R$ 120/h) e especializada (R$ 150/h) para motor, câmbio, injeção eletrônica.

9. **Critério de estoque**: manter em estoque peças com uso >= 3x/semana ou peças com lead time longo do fornecedor.

10. **Serviços terceirizados**: ar-condicionado, vidro elétrico, som automotivo. A oficina funciona como intermediário.

### 10.2 Regras de Fluxo

11. **OS pode regredir no fluxo**: se aparece problema adicional durante execução, a OS volta de "Em Serviço" para "Aguardando Orçamento".

12. **Veículo desmontado bloqueia elevador**: se a peça demora, o mecânico pode tirar o carro desmontado do elevador, mas isso aumenta risco e tempo.

13. **Diagnóstico e orçamento são etapas distintas**: o mecânico faz o diagnóstico; o orçamentista monta o orçamento. São pessoas e momentos diferentes.

14. **Queixa != Diagnóstico**: a descrição do cliente (queixa) deve ser registrada separadamente do diagnóstico técnico. Ambas são necessárias.

15. **Timeout de aprovação**: 1 semana sem resposta = cobrança ativa. 1 mês sem resposta = ameaça de estadia. Mas na prática não existe cobrança de estadia formalizada.

### 10.3 Regras Implícitas de Confiança

16. **Foto como prova**: mecânicos tiram foto da peça danificada e enviam ao cliente via WhatsApp para justificar o orçamento. Isso constrói confiança.

17. **Histórico de confiança afeta autonomia**: quanto mais antigo o relacionamento, mais liberdade o mecânico/dono tem para tomar decisões sem consultar o cliente.

18. **Código de peça como validação**: toda peça recebida de fornecedor deve ter o código conferido contra o catálogo. Peça com código errado é devolvida imediatamente.

---

## 11. Fontes e referências

### Validação de mercado

Os fluxos descritos pelos especialistas foram validados contra funcionalidades de sistemas reais de gestão de oficinas mecânicas no Brasil:

- [Ultracar](https://ultracar.com.br/) — sistema com quase 30 anos; fluxo entrada→diagnóstico→orçamento→execução→saída; baixa automática de estoque na aprovação
- [Oficina Integrada](https://www.oficinaintegrada.com.br/) — controle de estoque com alertas, OS com alertas a funcionários, comissões por setor
- [Soften Sistemas](https://www.softensistemas.com.br/sistema-para-oficina-mecanica) — baixa automática de estoque ao lançar peças na OS; geração de NFe e contas a receber na finalização
- [WSoft](https://wsoft.dev.br/) — workflow completo com fotos, checklist e notificações automáticas
- [GestãoClick](https://gestaoclick.com.br/programa-para-oficina-mecanica-e-auto-pecas/) — gestão ponta a ponta: orçamento→OS→peças→venda→financeiro

Funcionalidades presentes em todos os sistemas que estão fora do escopo do MVP: agendamento online, gestão financeira (contas a pagar/receber), emissão de NFe/NFSe, CRM.

### Regulamentações relevantes

- **CDC Art. 26, II** — prazo de 90 dias para reclamar de defeitos em serviços duráveis (valida a regra de garantia citada por Dona Marta)
- **CDC Art. 18-20** — responsabilidade por vícios do produto/serviço
- **Código Civil Art. 593-609** — prestação de serviço; Art. 700 — empreitada (quando o serviço tem resultado definido)
- **LGPD Art. 5, I; Art. 7; Art. 18; Art. 46** — CPF/CNPJ como dado pessoal, base legal para tratamento, direitos do titular, medidas de segurança

### DDD e Domain Storytelling

- [Domain Storytelling — Quick Start Guide](https://domainstorytelling.org/quick-start-guide)
- [Domain Storytelling — Open Practice Library](https://openpracticelibrary.com/practice/domain-storytelling/)
- [Domain Storytelling — DevIQ](https://deviq.com/domain-driven-design/domain-storytelling/)
- [Domain Storytelling book — InformIT](https://www.informit.com/store/domain-storytelling-a-collaborative-visual-and-agile-9780137458912)
- [Interviewing SMEs with DDD in Mind — Medium](https://lucavettor.medium.com/interviewing-subject-matter-experts-smes-with-domain-driven-design-ddd-in-mind-ea0a2557eb3e)
- [Domain Expert — DDD Practitioners Guide](https://ddd-practitioners.com/home/glossary/domain-expert/)

---

## Relação com Outros Documentos

- [Domain Storytelling — Diagramas](README.md) — Índice dos 5 diagramas no egon.io
- [Event Storming](../event-storming/) — Fluxos detalhados derivados das entrevistas
- [Workshop de Event Storming](../event-storming/workshop-event-storming.md) — Workshop progressivo de 10 passos com os mesmos especialistas
- [Glossário](../../requisitos/glossario.md) — Linguagem Ubíqua com todos os termos de domínio
- [Mapa de Contextos](../mapa-contextos.md) — Relação entre os 5 contextos delimitados
- [Modelo de Domínio](../modelo-dominio.md) — Diagramas de classes por agregado
- [ADR-007](../adr/007-organizacao-contextos-delimitados.md) — Organização dos contextos delimitados
