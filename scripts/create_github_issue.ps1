# Script para criar issue no GitHub via API REST
# Uso: ./create_github_issue.ps1 -Token "seu_github_token" -Owner "andrey-justo" -Repo "coding-tool-reasoning"

param(
    [Parameter(Mandatory=$true)]
    [string]$Token,
    
    [Parameter(Mandatory=$true)]
    [string]$Owner,
    
    [Parameter(Mandatory=$true)]
    [string]$Repo
)

$headers = @{
    "Authorization" = "Bearer $Token"
    "Accept" = "application/vnd.github.v3+json"
}

$title = "Implement Multi-Metric Code Quality Analyzer for RQ2-RQ4 Validation"

$body = @"
## Objetivo

Implementar um analisador multidimensional de qualidade de código para validar a efetividade da supervisão taxonômica em modernização de software legacy. O sistema deve agregar múltiplas métricas (SOLID, complexidade, code smells, análise semântica) e reportar Cohen's d e significância estatística.

## Contexto

Conforme Design de Pesquisa (docs/DESIGN_DE_PESQUISA.md), RQ2-RQ4 requerem validação de código gerado comparando:
- Condição supervisionada (com taxonomia SWE em 3 estágios MCP)
- Baseline (zero-shot LLM direto, temperatura=0.6)

Cada issue testado com 3 replicações (temperatura=0.6, seed fixa), resumindo métricas como mediana.

## Requisitos Técnicos

### Dimensões de Qualidade a Medir

1. **Arquitetura (25% peso)**
   - Violações SOLID: SRP, OCP, DIP (via AST + heurísticas)
   - Delta SOLID normalizado

2. **Complexidade (20% peso)**
   - Complexidade Ciclomática (Radon)
   - Complexidade Cognitiva
   - Linhas de código

3. **Análise Estática (25% peso)**
   - Code Smells (SonarQube ou análise local)
   - Security issues
   - Maintainability Index

4. **Semântica NLP (20% peso)**
   - Coesão semântica (similaridade comentários/código via embeddings)
   - Qualidade de nomes (detecção de nomes genéricos)
   - Cobertura de documentação

5. **Manutenibilidade (10% peso)**
   - Índice composto

### Saídas Esperadas

- **CodeQualityScore**: Dataclass com 10+ dimensões
- **compare_code_versions()**: Compara antes vs depois, retorna deltas
- **statistical_comparison_rq2()**: Cohen's d pareado, Wilcoxon test, p-value
- **MultiMetricAnalyzer**: Classe encapsulando análises

### Critério de Sucesso (RQ2)

✓ Mediana delta ≥10pp
✓ p-value < 0.05 (Wilcoxon signed-rank)
✓ Cohen's d ≥0.5 (efeito médio)

## Deliverables

1. `src/evaluation/multi_metric_analyzer.py` (500+ linhas)
   - CodeQualityScore dataclass
   - MultiMetricAnalyzer com 6+ métodos
   - Funções de comparação e estatística

2. `tests/unit/test_multi_metric_analyzer.py`
   - Testes de cada métrica individualmente
   - Testes de score composto
   - Testes de Cohen's d

3. `tests/examples/sample_code_analysis.py`
   - Exemplo de comparação antes/depois
   - Demonstração de RQ2 analysis completa

4. Documentação em `docs/METRICS.md`
   - Descrição de cada métrica
   - Pesos e normalização
   - Interpretação de resultados

## Dependências

\`\`\`
numpy>=1.20.0
scipy>=1.7.0
radon>=5.1.0
sentence-transformers>=2.2.0
scikit-learn>=1.0.0
\`\`\`

## Timeline

- [ ] Fase 1: Estrutura base + SOLID (semana 1)
- [ ] Fase 2: Complexidade + Code Smells (semana 2)
- [ ] Fase 3: NLP + Score Composto (semana 3)
- [ ] Fase 4: Testes + Documentação (semana 4)

## Referências

- Design de Pesquisa: docs/DESIGN_DE_PESQUISA.md
- Cohen's d: https://en.wikipedia.org/wiki/Effect_size#Cohen's_d
- Radon docs: https://radon.readthedocs.io/
- Sentence-Transformers: https://www.sbert.net/

## Acceptance Criteria

- [ ] CodeQualityScore dataclass implementado com todas as 10+ dimensões
- [ ] MultiMetricAnalyzer com analyze_solid_violations(), analyze_complexity(), analyze_code_smells(), analyze_semantic_quality()
- [ ] compare_code_versions() retorna dict com deltas para cada métrica
- [ ] statistical_comparison_rq2() retorna Cohen's d, Wilcoxon p-value e composite_improvement
- [ ] Testes unitários com cobertura ≥80%
- [ ] Exemplo funcional de análise RQ2 com dados simulados
- [ ] Documentação completa em METRICS.md explicando cada peso e normalização
"@

$labels = @("enhancement", "evaluation", "research")

$payload = @{
    "title" = $title
    "body" = $body
    "labels" = $labels
} | ConvertTo-Json

$uri = "https://api.github.com/repos/$Owner/$Repo/issues"

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $payload
    Write-Host "✓ Issue criada com sucesso!" -ForegroundColor Green
    Write-Host "Issue #$($response.number): $($response.title)" -ForegroundColor Cyan
    Write-Host "URL: $($response.html_url)" -ForegroundColor Cyan
    return $response
}
catch {
    Write-Host "✗ Erro ao criar issue:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    return $null
}
