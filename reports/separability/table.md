# Separability of attribution statistics (attack-attributable unauthorized B0 executions vs clean+neutral)

Positives: attack executions where B0 executed outside the allowed set and the same-seed clean execution was correct (steered). Negatives (default): clean, neutral, *resisted attacks* (attack text present, choice allowed) and the legitimate templates' authorized-influence condition — i.e. every execution a gate must not fire on. Variants with clean+neutral negatives only are listed separately. AUROC intervals: 95 % percentile bootstrap over templates (1000 resamples; few positive templates → intervals are optimistic). 'frozen' columns are the operating point of the development-calibrated threshold actually used by the gates (TPR / FPR, with FPR by negative kind). Regeneration-disagree is binary (TPR / FPR).

## dev-qwen14b  (positives 22, negatives 190 = {'clean': 72, 'neutral': 72, 'resisted': 34, 'legit_attack': 12}, templates 24)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| candidate-relative log-odds change R | 0.970 | 0.912–0.997 | 0.801 | 0.121 | 8.409 | 0.955 | 0.04/0.06/0.50/0.25 |
| TV distance D | 0.969 | 0.896–0.999 | 0.818 | 0.147 | 0.000 | 0.864 | 0.06/0.03/0.29/0.25 |
| enhanced R (closure on history) | 0.964 | 0.907–0.996 | 0.794 | 0.142 | 7.589 | 0.955 | 0.03/0.07/0.50/0.25 |
| TV distance, free fields blanked | 0.959 | 0.886–0.996 | 0.774 | 0.137 | 0.175 | 0.773 | 0.07/0.03/0.03/0.25 |
| R, free fields blanked | 0.889 | 0.676–1.000 | 0.809 | 0.716 | 12.531 | 0.818 | 0.01/0.06/0.09/0.25 |
| chosen-action log-prob drop (joint deletion) | 0.725 | 0.549–0.865 | 0.313 | 0.689 | 159.505 | 0.227 | 0.04/0.06/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.581 | 0.376–0.813 | 0.222 | 0.989 | 156.081 | 0.182 | 0.04/0.06/0.00/0.00 |
| max single-source LOO drop | 0.550 | 0.385–0.716 | 0.133 | 0.989 | 129.392 | 0.045 | 0.04/0.06/0.12/0.00 |
| CausalArmor margin (span − user request, per token) | 0.482 | 0.297–0.638 | 0.098 | 0.847 | 1.155 | 0.045 | 0.03/0.07/0.09/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.042 | – | 1.000 | 0.03/0.03/0.03/0.25 |

## dev-qwen14b (clean+neutral negatives only)  (positives 22, negatives 144 = {'clean': 72, 'neutral': 72, 'resisted': 0, 'legit_attack': 0}, templates 24)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| candidate-relative log-odds change R | 0.995 | 0.976–1.000 | 0.971 | 0.035 | 8.409 | 0.955 | 0.04/0.06/0.00/0.00 |
| enhanced R (closure on history) | 0.988 | 0.944–1.000 | 0.952 | 0.049 | 7.589 | 0.955 | 0.03/0.07/0.00/0.00 |
| TV distance D | 0.982 | 0.925–1.000 | 0.919 | 0.104 | 0.000 | 0.864 | 0.06/0.03/0.00/0.00 |
| TV distance, free fields blanked | 0.968 | 0.906–0.998 | 0.877 | 0.125 | 0.175 | 0.773 | 0.07/0.03/0.00/0.00 |
| R, free fields blanked | 0.895 | 0.688–1.000 | 0.862 | 0.708 | 12.531 | 0.818 | 0.01/0.06/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.711 | 0.534–0.846 | 0.335 | 0.701 | 159.505 | 0.227 | 0.04/0.06/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.579 | 0.391–0.805 | 0.246 | 0.986 | 156.081 | 0.182 | 0.04/0.06/0.00/0.00 |
| max single-source LOO drop | 0.549 | 0.395–0.706 | 0.162 | 0.986 | 129.392 | 0.045 | 0.04/0.06/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.490 | 0.311–0.638 | 0.127 | 0.840 | 1.155 | 0.045 | 0.03/0.07/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.028 | – | 1.000 | 0.03/0.03/0.00/0.00 |

## dev-llama8b  (positives 18, negatives 182 = {'clean': 66, 'neutral': 70, 'resisted': 34, 'legit_attack': 12}, templates 24)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance, free fields blanked | 0.982 | 0.938–1.000 | 0.885 | 0.132 | 0.207 | 0.889 | 0.05/0.03/0.21/0.00 |
| TV distance D | 0.972 | 0.935–0.993 | 0.811 | 0.165 | 0.164 | 0.944 | 0.05/0.04/0.24/0.08 |
| R, free fields blanked | 0.971 | 0.922–0.999 | 0.841 | 0.137 | 3.909 | 0.722 | 0.06/0.03/0.18/0.00 |
| enhanced R (closure on history) | 0.950 | 0.904–0.987 | 0.702 | 0.319 | 5.471 | 0.722 | 0.05/0.04/0.18/0.00 |
| candidate-relative log-odds change R | 0.946 | 0.875–0.990 | 0.718 | 0.363 | 5.682 | 0.833 | 0.05/0.04/0.29/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.552 | 0.358–0.760 | 0.152 | 0.758 | 227.879 | 0.111 | 0.02/0.07/0.15/0.00 |
| joint-deletion drop (chosen action) | 0.390 | 0.212–0.654 | 0.106 | 1.000 | 226.117 | 0.056 | 0.00/0.09/0.15/0.00 |
| max single-source LOO drop | 0.339 | 0.212–0.500 | 0.095 | 1.000 | 162.812 | 0.056 | 0.00/0.09/0.18/0.08 |
| CausalArmor margin (span − user request, per token) | 0.273 | 0.146–0.441 | 0.087 | 0.989 | 1.344 | 0.056 | 0.00/0.09/0.24/0.08 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.044 | – | 1.000 | 0.05/0.04/0.06/0.00 |

## dev-llama8b (clean+neutral negatives only)  (positives 18, negatives 136 = {'clean': 66, 'neutral': 70, 'resisted': 0, 'legit_attack': 0}, templates 24)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 0.987 | 0.957–1.000 | 0.928 | 0.140 | 0.164 | 0.944 | 0.05/0.04/0.00/0.00 |
| TV distance, free fields blanked | 0.987 | 0.944–1.000 | 0.948 | 0.118 | 0.207 | 0.889 | 0.05/0.03/0.00/0.00 |
| R, free fields blanked | 0.981 | 0.952–1.000 | 0.901 | 0.088 | 3.909 | 0.722 | 0.06/0.03/0.00/0.00 |
| candidate-relative log-odds change R | 0.967 | 0.923–0.997 | 0.842 | 0.287 | 5.682 | 0.833 | 0.05/0.04/0.00/0.00 |
| enhanced R (closure on history) | 0.967 | 0.931–0.998 | 0.849 | 0.272 | 5.471 | 0.722 | 0.05/0.04/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.559 | 0.372–0.768 | 0.222 | 0.750 | 227.879 | 0.111 | 0.02/0.07/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.407 | 0.232–0.664 | 0.162 | 1.000 | 226.117 | 0.056 | 0.00/0.09/0.00/0.00 |
| max single-source LOO drop | 0.355 | 0.238–0.504 | 0.145 | 1.000 | 162.812 | 0.056 | 0.00/0.09/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.292 | 0.166–0.443 | 0.107 | 0.985 | 1.344 | 0.056 | 0.00/0.09/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.044 | – | 1.000 | 0.05/0.04/0.00/0.00 |

## conf-qwen14b  (positives 9, negatives 63 = {'clean': 24, 'neutral': 24, 'resisted': 9, 'legit_attack': 6}, templates 8)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 0.996 | 0.965–1.000 | 0.980 | 0.032 | 0.000 | 1.000 | 0.00/0.00/0.56/0.00 |
| enhanced R (closure on history) | 0.963 | 0.882–1.000 | 0.802 | 0.143 | 7.589 | 1.000 | 0.04/0.04/0.89/0.00 |
| candidate-relative log-odds change R | 0.958 | 0.859–1.000 | 0.781 | 0.143 | 8.409 | 1.000 | 0.04/0.04/0.89/0.00 |
| TV distance, free fields blanked | 0.910 | 0.674–0.996 | 0.646 | 0.190 | 0.175 | 0.667 | 0.12/0.00/0.67/0.00 |
| R, free fields blanked | 0.764 | 0.408–0.989 | 0.509 | 0.540 | 12.531 | 0.556 | 0.12/0.00/0.78/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.616 | 0.338–0.879 | 0.158 | 0.524 | 159.505 | 0.000 | 0.00/0.04/0.00/0.00 |
| max single-source LOO drop | 0.596 | 0.342–0.831 | 0.152 | 1.000 | 129.392 | 0.000 | 0.12/0.12/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.577 | 0.325–0.844 | 0.143 | 1.000 | 156.081 | 0.000 | 0.00/0.00/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.534 | 0.257–0.767 | 0.138 | 0.778 | 1.155 | 0.000 | 0.12/0.17/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.000 | – | 1.000 | 0.00/0.00/0.00/0.00 |

## conf-qwen14b (clean+neutral negatives only)  (positives 9, negatives 48 = {'clean': 24, 'neutral': 24, 'resisted': 0, 'legit_attack': 0}, templates 8)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 1.000 | 1.000–1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.00/0.00/0.00/0.00 |
| candidate-relative log-odds change R | 0.998 | 0.990–1.000 | 0.989 | 0.021 | 8.409 | 1.000 | 0.04/0.04/0.00/0.00 |
| enhanced R (closure on history) | 0.998 | 0.991–1.000 | 0.989 | 0.021 | 7.589 | 1.000 | 0.04/0.04/0.00/0.00 |
| TV distance, free fields blanked | 0.951 | 0.712–1.000 | 0.830 | 0.125 | 0.175 | 0.667 | 0.12/0.00/0.00/0.00 |
| R, free fields blanked | 0.806 | 0.446–1.000 | 0.629 | 0.521 | 12.531 | 0.556 | 0.12/0.00/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.597 | 0.352–0.854 | 0.191 | 0.562 | 159.505 | 0.000 | 0.00/0.04/0.00/0.00 |
| max single-source LOO drop | 0.583 | 0.354–0.804 | 0.186 | 1.000 | 129.392 | 0.000 | 0.12/0.12/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.567 | 0.343–0.817 | 0.177 | 1.000 | 156.081 | 0.000 | 0.00/0.00/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.553 | 0.286–0.785 | 0.181 | 0.771 | 1.155 | 0.000 | 0.12/0.17/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.000 | – | 1.000 | 0.00/0.00/0.00/0.00 |

## conf-llama8b  (positives 7, negatives 64 = {'clean': 24, 'neutral': 24, 'resisted': 10, 'legit_attack': 6}, templates 8)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 0.987 | 0.956–1.000 | 0.920 | 0.078 | 0.164 | 1.000 | 0.17/0.04/0.20/0.50 |
| TV distance, free fields blanked | 0.984 | 0.897–1.000 | 0.896 | 0.062 | 0.207 | 1.000 | 0.04/0.00/0.40/0.50 |
| enhanced R (closure on history) | 0.853 | 0.748–0.968 | 0.336 | 0.297 | 5.471 | 0.143 | 0.00/0.00/0.60/0.17 |
| R, free fields blanked | 0.846 | 0.650–1.000 | 0.495 | 0.266 | 3.909 | 0.714 | 0.00/0.00/0.90/0.50 |
| candidate-relative log-odds change R | 0.839 | 0.739–0.943 | 0.402 | 0.328 | 5.682 | 0.143 | 0.00/0.00/0.50/0.17 |
| chosen-action log-prob drop (joint deletion) | 0.603 | 0.214–0.985 | 0.312 | 0.656 | 227.879 | 0.143 | 0.00/0.00/0.10/0.00 |
| max single-source LOO drop | 0.464 | 0.203–0.727 | 0.110 | 0.984 | 162.812 | 0.000 | 0.00/0.00/0.10/0.33 |
| joint-deletion drop (chosen action) | 0.440 | 0.185–0.694 | 0.105 | 0.984 | 226.117 | 0.000 | 0.00/0.00/0.10/0.00 |
| CausalArmor margin (span − user request, per token) | 0.386 | 0.121–0.621 | 0.100 | 0.797 | 1.344 | 0.000 | 0.00/0.12/0.10/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.062 | – | 1.000 | 0.04/0.00/0.00/0.50 |

## conf-llama8b (clean+neutral negatives only)  (positives 7, negatives 48 = {'clean': 24, 'neutral': 24, 'resisted': 0, 'legit_attack': 0}, templates 8)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance, free fields blanked | 1.000 | 1.000–1.000 | 1.000 | 0.000 | 0.207 | 1.000 | 0.04/0.00/0.00/0.00 |
| TV distance D | 0.988 | 0.958–1.000 | 0.937 | 0.062 | 0.164 | 1.000 | 0.17/0.04/0.00/0.00 |
| R, free fields blanked | 0.976 | 0.875–1.000 | 0.896 | 0.083 | 3.909 | 0.714 | 0.00/0.00/0.00/0.00 |
| candidate-relative log-odds change R | 0.961 | 0.885–1.000 | 0.862 | 0.188 | 5.682 | 0.143 | 0.00/0.00/0.00/0.00 |
| enhanced R (closure on history) | 0.961 | 0.885–1.000 | 0.859 | 0.167 | 5.471 | 0.143 | 0.00/0.00/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.607 | 0.250–0.990 | 0.364 | 0.688 | 227.879 | 0.143 | 0.00/0.00/0.00/0.00 |
| max single-source LOO drop | 0.497 | 0.229–0.729 | 0.154 | 0.979 | 162.812 | 0.000 | 0.00/0.00/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.464 | 0.229–0.693 | 0.142 | 0.979 | 226.117 | 0.000 | 0.00/0.00/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.405 | 0.151–0.604 | 0.134 | 0.812 | 1.344 | 0.000 | 0.00/0.12/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.021 | – | 1.000 | 0.04/0.00/0.00/0.00 |

## pooled-qwen14b  (positives 31, negatives 253 = {'clean': 96, 'neutral': 96, 'resisted': 43, 'legit_attack': 18}, templates 32)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 0.974 | 0.932–0.997 | 0.847 | 0.130 | 0.000 | 0.903 | 0.04/0.02/0.35/0.17 |
| candidate-relative log-odds change R | 0.968 | 0.931–0.991 | 0.805 | 0.130 | 8.409 | 0.968 | 0.04/0.05/0.58/0.17 |
| enhanced R (closure on history) | 0.966 | 0.921–0.993 | 0.803 | 0.146 | 7.589 | 0.968 | 0.03/0.06/0.58/0.17 |
| TV distance, free fields blanked | 0.951 | 0.891–0.992 | 0.750 | 0.158 | 0.175 | 0.742 | 0.08/0.02/0.16/0.17 |
| R, free fields blanked | 0.878 | 0.726–0.984 | 0.716 | 0.692 | 12.531 | 0.742 | 0.04/0.04/0.23/0.17 |
| chosen-action log-prob drop (joint deletion) | 0.686 | 0.531–0.822 | 0.259 | 0.648 | 159.505 | 0.161 | 0.03/0.05/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.573 | 0.453–0.731 | 0.194 | 0.992 | 156.081 | 0.129 | 0.03/0.04/0.00/0.00 |
| max single-source LOO drop | 0.555 | 0.416–0.687 | 0.129 | 0.992 | 129.392 | 0.032 | 0.06/0.07/0.09/0.00 |
| CausalArmor margin (span − user request, per token) | 0.489 | 0.344–0.629 | 0.101 | 0.866 | 1.155 | 0.032 | 0.05/0.09/0.07/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.032 | – | 1.000 | 0.02/0.02/0.02/0.17 |

## pooled-llama8b  (positives 25, negatives 246 = {'clean': 90, 'neutral': 94, 'resisted': 44, 'legit_attack': 18}, templates 32)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance, free fields blanked | 0.981 | 0.946–1.000 | 0.867 | 0.142 | 0.207 | 0.920 | 0.04/0.02/0.25/0.17 |
| TV distance D | 0.972 | 0.939–0.991 | 0.800 | 0.077 | 0.164 | 0.960 | 0.08/0.04/0.23/0.22 |
| R, free fields blanked | 0.945 | 0.902–0.982 | 0.740 | 0.199 | 3.909 | 0.720 | 0.04/0.02/0.34/0.17 |
| enhanced R (closure on history) | 0.918 | 0.843–0.969 | 0.602 | 0.309 | 5.471 | 0.560 | 0.03/0.03/0.27/0.06 |
| candidate-relative log-odds change R | 0.915 | 0.837–0.967 | 0.612 | 0.333 | 5.682 | 0.640 | 0.03/0.03/0.34/0.06 |
| chosen-action log-prob drop (joint deletion) | 0.568 | 0.421–0.729 | 0.166 | 0.744 | 227.879 | 0.120 | 0.01/0.05/0.14/0.00 |
| joint-deletion drop (chosen action) | 0.408 | 0.288–0.577 | 0.099 | 0.980 | 226.117 | 0.040 | 0.00/0.06/0.14/0.00 |
| max single-source LOO drop | 0.374 | 0.257–0.517 | 0.092 | 0.980 | 162.812 | 0.040 | 0.00/0.06/0.16/0.17 |
| CausalArmor margin (span − user request, per token) | 0.319 | 0.189–0.456 | 0.086 | 0.976 | 1.344 | 0.040 | 0.00/0.10/0.20/0.06 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.049 | – | 1.000 | 0.04/0.03/0.05/0.17 |

## pooled-qwen14b (clean+neutral negatives only)  (positives 31, negatives 192 = {'clean': 96, 'neutral': 96, 'resisted': 0, 'legit_attack': 0}, templates 32)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| candidate-relative log-odds change R | 0.995 | 0.982–1.000 | 0.973 | 0.036 | 8.409 | 0.968 | 0.04/0.05/0.00/0.00 |
| enhanced R (closure on history) | 0.991 | 0.969–1.000 | 0.960 | 0.047 | 7.589 | 0.968 | 0.03/0.06/0.00/0.00 |
| TV distance D | 0.987 | 0.959–1.000 | 0.938 | 0.078 | 0.000 | 0.903 | 0.04/0.02/0.00/0.00 |
| TV distance, free fields blanked | 0.963 | 0.910–0.997 | 0.856 | 0.135 | 0.175 | 0.742 | 0.08/0.02/0.00/0.00 |
| R, free fields blanked | 0.892 | 0.745–0.996 | 0.808 | 0.688 | 12.531 | 0.742 | 0.04/0.04/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.671 | 0.520–0.799 | 0.283 | 0.667 | 159.505 | 0.161 | 0.03/0.05/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.569 | 0.458–0.712 | 0.220 | 0.990 | 156.081 | 0.129 | 0.03/0.04/0.00/0.00 |
| max single-source LOO drop | 0.551 | 0.426–0.669 | 0.158 | 0.990 | 129.392 | 0.032 | 0.06/0.07/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.498 | 0.365–0.635 | 0.131 | 0.865 | 1.155 | 0.032 | 0.05/0.09/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.021 | – | 1.000 | 0.02/0.02/0.00/0.00 |

## pooled-llama8b (clean+neutral negatives only)  (positives 25, negatives 184 = {'clean': 90, 'neutral': 94, 'resisted': 0, 'legit_attack': 0}, templates 32)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance, free fields blanked | 0.991 | 0.960–1.000 | 0.964 | 0.109 | 0.207 | 0.920 | 0.04/0.02/0.00/0.00 |
| TV distance D | 0.985 | 0.959–1.000 | 0.916 | 0.033 | 0.164 | 0.960 | 0.08/0.04/0.00/0.00 |
| R, free fields blanked | 0.977 | 0.957–0.998 | 0.874 | 0.092 | 3.909 | 0.720 | 0.04/0.02/0.00/0.00 |
| candidate-relative log-odds change R | 0.951 | 0.895–0.989 | 0.784 | 0.239 | 5.682 | 0.640 | 0.03/0.03/0.00/0.00 |
| enhanced R (closure on history) | 0.948 | 0.894–0.988 | 0.793 | 0.239 | 5.471 | 0.560 | 0.03/0.03/0.00/0.00 |
| chosen-action log-prob drop (joint deletion) | 0.570 | 0.442–0.733 | 0.232 | 0.745 | 227.879 | 0.120 | 0.01/0.05/0.00/0.00 |
| joint-deletion drop (chosen action) | 0.424 | 0.300–0.585 | 0.147 | 0.978 | 226.117 | 0.040 | 0.00/0.06/0.00/0.00 |
| max single-source LOO drop | 0.390 | 0.273–0.526 | 0.136 | 0.978 | 162.812 | 0.040 | 0.00/0.06/0.00/0.00 |
| CausalArmor margin (span − user request, per token) | 0.336 | 0.211–0.464 | 0.108 | 0.967 | 1.344 | 0.040 | 0.00/0.10/0.00/0.00 |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.038 | – | 1.000 | 0.04/0.03/0.00/0.00 |

## pooled-all  (positives 56, negatives 499 = {'clean': 186, 'neutral': 190, 'resisted': 87, 'legit_attack': 36}, templates 32)

| statistic | AUROC | 95 % CI (template bootstrap) | AUPRC | FPR @ 95 % TPR (fitted) | frozen thr | TPR @ frozen | FPR @ frozen (clean/neutral/resisted/legit) |
|---|---|---|---|---|---|---|---|
| TV distance D | 0.957 | 0.906–0.987 | 0.799 | 0.425 | – | – | – |
| TV distance, free fields blanked | 0.951 | 0.899–0.984 | 0.730 | 0.253 | – | – | – |
| candidate-relative log-odds change R | 0.928 | 0.891–0.960 | 0.653 | 0.339 | – | – | – |
| enhanced R (closure on history) | 0.928 | 0.895–0.954 | 0.650 | 0.365 | – | – | – |
| R, free fields blanked | 0.873 | 0.798–0.930 | 0.567 | 0.553 | – | – | – |
| chosen-action log-prob drop (joint deletion) | 0.626 | 0.496–0.734 | 0.168 | 0.723 | – | – | – |
| joint-deletion drop (chosen action) | 0.495 | 0.378–0.641 | 0.111 | 0.986 | – | – | – |
| max single-source LOO drop | 0.468 | 0.360–0.583 | 0.097 | 0.986 | – | – | – |
| CausalArmor margin (span − user request, per token) | 0.396 | 0.273–0.497 | 0.086 | 0.958 | – | – | – |
| fresh regeneration disagrees (binary) | TPR 1.000 | – | – | FPR 0.040 | – | 1.000 | 0.03/0.03/0.03/0.17 |

