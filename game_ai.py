# game_ai.py
"""
Motore AI generico per giochi a turni a due giocatori (usato dal Tris).

Algoritmi disponibili:
    * ``random``     - mossa casuale
    * ``heuristic``  - valuta solo la posizione dopo una mossa (greedy)
    * ``minimax``    - minimax con iterative deepening e tabella di
                       trasposizione (memo) se lo stato espone ``key()``
    * ``alpha_beta`` - potatura alpha-beta con ordinamento delle mosse

Novità della v3:
    * a parità di valore la mossa viene scelta a caso (CPU meno prevedibile);
    * ``blunder_rate``: probabilità di "sbagliare" apposta (difficoltà facili);
    * l'iterative deepening usa solo le profondità completate entro il tempo
      (prima una ricerca interrotta a metà poteva sovrascrivere la mossa buona);
    * ``GameAI.for_level("easy" | "medium" | "hard")`` crea preset pronti;
    * ``__slots__`` ora funziona davvero anche nelle sottoclassi di ``GameState``.
"""
from __future__ import annotations

import copy
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Hashable
from enum import Enum
from typing import Any, Dict, List, Tuple


class AIAlgorithm(Enum):
    """Enumerazione degli algoritmi AI disponibili."""
    RANDOM = "random"
    MINIMAX = "minimax"
    ALPHA_BETA = "alpha_beta"
    HEURISTIC = "heuristic"


class GameResult(Enum):
    """Risultati possibili di una partita."""
    WIN = 1
    LOSS = -1
    DRAW = 0
    ONGOING = None


class GameState(ABC):
    """Classe astratta per rappresentare lo stato di un gioco."""

    __slots__ = ()  # permette alle sottoclassi di usare __slots__ davvero

    @abstractmethod
    def get_legal_moves(self) -> List[Any]:
        """Restituisce la lista delle mosse legali disponibili."""
        pass

    @abstractmethod
    def make_move(self, move: Any) -> GameState:
        """Esegue una mossa e restituisce il nuovo stato del gioco."""
        pass

    @abstractmethod
    def is_terminal(self) -> bool:
        """Verifica se lo stato è terminale (partita finita)."""
        pass

    @abstractmethod
    def get_result(self, player: int) -> GameResult:
        """Restituisce il risultato della partita per il giocatore specificato."""
        pass

    @abstractmethod
    def get_current_player(self) -> int:
        """Restituisce l'ID del giocatore corrente."""
        pass

    @abstractmethod
    def evaluate_position(self, player: int) -> float:
        """Valuta la posizione corrente per il giocatore specificato."""
        pass

    def copy(self) -> GameState:
        """Crea una copia profonda dello stato di gioco."""
        return copy.deepcopy(self)

    def key(self) -> Hashable | None:
        """
        Chiave hashable che identifica lo stato (opzionale).

        Se restituisce un valore diverso da ``None`` il minimax memorizza i
        risultati già calcolati (tabella di trasposizione), evitando di
        rianalizzare la stessa posizione raggiunta con ordini di mosse diversi.
        """
        return None


class GameAI:
    """
    Motore AI per giochi con supporto per minimax, alpha-beta pruning,
    deepening iterativo, euristica e mosse casuali.
    """

    __slots__ = (
        'algorithm', 'difficulty', 'time_limit', 'player_id',
        'nodes_evaluated', 'start_time', 'blunder_rate', 'rng',
        '_memo', '_aborted'
    )

    def __init__(
        self,
        algorithm: str = "minimax",
        difficulty: int = 3,
        time_limit: float = 5.0,
        player_id: int = -1,
        blunder_rate: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        """
        Inizializza l'AI del gioco.

        Args:
            algorithm: Algoritmo da utilizzare ('minimax', 'alpha_beta', 'random', 'heuristic')
            difficulty: Profondità di ricerca (1-9)
            time_limit: Tempo massimo per trovare una mossa in secondi
            player_id: ID del giocatore AI
            blunder_rate: Probabilità (0-1) di giocare una mossa casuale
            rng: Generatore casuale (utile nei test per risultati ripetibili)
        """
        if isinstance(algorithm, AIAlgorithm):
            self.algorithm: AIAlgorithm = algorithm
        else:
            alg_str = str(algorithm).lower()
            found: AIAlgorithm | None = None
            for alg in AIAlgorithm:
                if alg.value == alg_str:
                    found = alg
                    break
            if found is None:
                found = AIAlgorithm.MINIMAX
                print(
                    f"[GameAI] Warning: algoritmo '{algorithm}' non riconosciuto. "
                    f"Uso '{found.value}'."
                )
            self.algorithm = found

        self.difficulty: int = max(1, min(9, difficulty))
        self.time_limit: float = max(0.01, float(time_limit))
        self.player_id: int = player_id
        self.blunder_rate: float = max(0.0, min(1.0, blunder_rate))
        self.rng: random.Random = rng or random.Random()
        self.nodes_evaluated: int = 0
        self.start_time: float = 0.0
        self._memo: Dict[Any, float] = {}
        self._aborted: bool = False

    @classmethod
    def for_level(cls, level: str, player_id: int = -1,
                  rng: random.Random | None = None) -> GameAI:
        """
        Preset pronti all'uso.

        * ``easy``   - euristica greedy che sbaglia una mossa su tre
        * ``medium`` - minimax a profondità 2 con qualche errore
        * ``hard``   - minimax completo: nel Tris è imbattibile
        """
        presets = {
            "easy": dict(algorithm="heuristic", difficulty=1, blunder_rate=0.35),
            "medium": dict(algorithm="minimax", difficulty=2, blunder_rate=0.12),
            "hard": dict(algorithm="minimax", difficulty=9, blunder_rate=0.0),
        }
        cfg = presets.get(level, presets["medium"])
        return cls(player_id=player_id, rng=rng, **cfg)  # type: ignore[arg-type]

    def get_best_move(self, state: GameState) -> Any | None:
        """
        Calcola la miglior mossa per lo stato di gioco dato.

        Args:
            state: Lo stato corrente del gioco

        Returns:
            La miglior mossa trovata, o None se non disponibile
        """
        try:
            legal_moves = list(state.get_legal_moves())
        except Exception:
            return None

        if not legal_moves:
            return None

        self.nodes_evaluated = 0
        self.start_time = time.perf_counter()
        self._memo = {}
        self._aborted = False

        if self.blunder_rate and self.rng.random() < self.blunder_rate:
            return self.rng.choice(legal_moves)

        try:
            if self.algorithm == AIAlgorithm.RANDOM:
                return self._random_move(legal_moves)
            elif self.algorithm == AIAlgorithm.MINIMAX:
                return self._minimax_move(state, legal_moves)
            elif self.algorithm == AIAlgorithm.ALPHA_BETA:
                return self._alpha_beta_move(state, legal_moves)
            elif self.algorithm == AIAlgorithm.HEURISTIC:
                return self._heuristic_move(state, legal_moves)
            return self.rng.choice(legal_moves)
        except Exception:
            # fallback robusto
            try:
                return self.rng.choice(legal_moves)
            except Exception:
                return None

    def _random_move(self, legal_moves: List[Any]) -> Any:
        """Seleziona una mossa casuale."""
        return self.rng.choice(legal_moves)

    def _pick(self, scored: List[Tuple[float, Any]]) -> Any:
        """Sceglie a caso tra le mosse con il valore massimo (tie-break)."""
        best_value = max(v for v, _ in scored)
        best = [m for v, m in scored if v >= best_value - 1e-9]
        return self.rng.choice(best)

    def _minimax_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando minimax con deepening iterativo.

        Solo le profondità completate entro il tempo limite vengono usate.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        best_move: Any | None = None
        max_depth = max(1, self.difficulty)
        # Se la profondità copre tutta la partita rimasta (come nel Tris, dove
        # ogni mossa occupa una casella) basta una sola ricerca completa.
        first_depth = max_depth if max_depth >= len(legal_moves) else 1

        # Deepening iterativo: prova profondità 1, 2, 3... fino a max_depth
        for current_depth in range(first_depth, max_depth + 1):
            if self._is_time_up():
                break
            scored: List[Tuple[float, Any]] = []
            for move in legal_moves:
                try:
                    new_state = state.make_move(move)
                    scored.append((self._minimax(new_state, current_depth - 1, False), move))
                except Exception:
                    continue
            if self._aborted:
                break  # profondità incompleta: si tiene il risultato precedente
            if scored:
                best_move = self._pick(scored)
            if all(abs(v) >= 1000 for v, _ in scored):
                break  # esito già certo per ogni mossa: inutile scendere ancora

        return best_move if best_move is not None else self.rng.choice(legal_moves)

    def _alpha_beta_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando alpha-beta pruning con deepening iterativo.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        best_move: Any | None = None
        max_depth = max(1, self.difficulty)

        # Deepening iterativo con ordinamento delle mosse
        for current_depth in range(1, max_depth + 1):
            if self._is_time_up():
                break

            # Ordina le mosse per migliorare il pruning
            ordered_moves = self._order_moves(state, legal_moves)

            depth_best_move: Any | None = None
            depth_best_value: float = float('-inf')
            alpha: float = float('-inf')
            beta: float = float('inf')

            for move in ordered_moves:
                try:
                    new_state = state.make_move(move)
                    value = self._alpha_beta(new_state, current_depth - 1, alpha, beta, False)
                    if value > depth_best_value:
                        depth_best_value = value
                        depth_best_move = move
                    alpha = max(alpha, value)
                except Exception:
                    continue

            if self._aborted:
                break
            if depth_best_move is not None:
                best_move = depth_best_move

        return best_move if best_move is not None else self.rng.choice(legal_moves)

    def _heuristic_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando un'euristica di valutazione diretta.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        scored: List[Tuple[float, Any]] = []
        for move in legal_moves:
            try:
                new_state = state.make_move(move)
                scored.append((new_state.evaluate_position(self.player_id), move))
            except Exception:
                continue
        return self._pick(scored) if scored else self.rng.choice(legal_moves)

    def _order_moves(self, state: GameState, moves: List[Any]) -> List[Any]:
        """
        Ordina le mosse per migliorare l'efficacia dell'alpha-beta pruning.
        Le mosse centrali e gli angoli hanno priorità nel TicTacToe.

        Args:
            state: Lo stato corrente del gioco
            moves: Lista delle mosse da ordinare

        Returns:
            Lista delle mosse ordinate
        """
        # Verifica se è una mossa di TicTacToe (tupla di coordinate)
        if moves and isinstance(moves[0], tuple) and len(moves[0]) == 2:
            # Priorità: centro, poi angoli, poi bordi
            center_moves: List[Any] = []
            corner_moves: List[Any] = []
            edge_moves: List[Any] = []

            for move in moves:
                if isinstance(move, tuple) and len(move) == 2:
                    row, col = move
                    if row == 1 and col == 1:  # Centro
                        center_moves.append(move)
                    elif row in (0, 2) and col in (0, 2):  # Angoli
                        corner_moves.append(move)
                    else:  # Bordi
                        edge_moves.append(move)

            return center_moves + corner_moves + edge_moves

        return moves

    def _evaluate_terminal(self, state: GameState, depth: int) -> float:
        """
        Valuta uno stato terminale o non più esplorabile.
        Logica condivisa tra minimax e alpha-beta.

        Args:
            state: Lo stato da valutare
            depth: Profondità rimanente: vincere prima vale di più

        Returns:
            Il valore della posizione
        """
        if state.is_terminal():
            result = state.get_result(self.player_id)
            if result == GameResult.WIN:
                return 1000 + depth
            elif result == GameResult.LOSS:
                return -1000 - depth
            else:
                return 0
        else:
            try:
                return state.evaluate_position(self.player_id)
            except Exception:
                return 0.0

    def _minimax(self, state: GameState, depth: int, maximizing: bool) -> float:
        """
        Algoritmo minimax ricorsivo con tabella di trasposizione opzionale.

        Args:
            state: Lo stato corrente del gioco
            depth: Profondità rimanente di ricerca
            maximizing: True se è il turno del massimizzatore

        Returns:
            Il valore minimax dello stato
        """
        self.nodes_evaluated += 1

        if self._is_time_up():
            self._aborted = True
            return self._evaluate_terminal(state, depth)
        if depth == 0 or state.is_terminal():
            return self._evaluate_terminal(state, depth)

        state_key = state.key()
        memo_key = (state_key, depth, maximizing) if state_key is not None else None
        if memo_key is not None and memo_key in self._memo:
            return self._memo[memo_key]

        values = []
        for move in state.get_legal_moves():
            try:
                values.append(self._minimax(state.make_move(move), depth - 1, not maximizing))
            except Exception:
                continue
            if self._aborted:
                break
        if not values:
            return self._evaluate_terminal(state, depth)
        result = max(values) if maximizing else min(values)
        if memo_key is not None and not self._aborted:
            self._memo[memo_key] = result
        return result

    def _alpha_beta(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
        maximizing: bool
    ) -> float:
        """
        Algoritmo alpha-beta pruning ricorsivo.

        Args:
            state: Lo stato corrente del gioco
            depth: Profondità rimanente di ricerca
            alpha: Valore alfa (lower bound del massimizzatore)
            beta: Valore beta (upper bound del minimizzatore)
            maximizing: True se è il turno del massimizzatore

        Returns:
            Il valore alpha-beta dello stato
        """
        self.nodes_evaluated += 1

        if self._is_time_up():
            self._aborted = True
            return self._evaluate_terminal(state, depth)
        if depth == 0 or state.is_terminal():
            return self._evaluate_terminal(state, depth)

        if maximizing:
            max_value: float = float('-inf')
            for move in self._order_moves(state, state.get_legal_moves()):
                try:
                    value = self._alpha_beta(state.make_move(move), depth - 1, alpha, beta, False)
                except Exception:
                    continue
                max_value = max(max_value, value)
                alpha = max(alpha, value)
                if beta <= alpha or self._aborted:
                    break
            return max_value
        else:
            min_value: float = float('inf')
            for move in self._order_moves(state, state.get_legal_moves()):
                try:
                    value = self._alpha_beta(state.make_move(move), depth - 1, alpha, beta, True)
                except Exception:
                    continue
                min_value = min(min_value, value)
                beta = min(beta, value)
                if beta <= alpha or self._aborted:
                    break
            return min_value

    def _is_time_up(self) -> bool:
        """Verifica se il tempo massimo è stato superato."""
        return time.perf_counter() - self.start_time > self.time_limit

    def get_stats(self) -> Dict[str, Any]:
        """
        Restituisce statistiche sull'ultima ricerca effettuata.

        Returns:
            Dizionario con statistiche (algoritmo, difficoltà, nodi valutati, tempo)
        """
        return {
            "algorithm": self.algorithm.value,
            "difficulty": self.difficulty,
            "nodes_evaluated": self.nodes_evaluated,
            "time_taken": time.perf_counter() - self.start_time
        }


class TicTacToeState(GameState):
    """
    Implementazione dello stato di gioco per TicTacToe.
    Supporta valutazione posizionale, cache delle mosse legali.
    """

    __slots__ = ('board', 'current_player', '_legal_moves_cache', '_cache_valid')

    def __init__(
        self,
        board: List[List[int | None]] | None = None,
        current_player: int = 1
    ) -> None:
        """
        Inizializza lo stato di TicTacToe.

        Args:
            board: Matrice 3x3 rappresentante la scacchiera (None per vuota)
            current_player: ID del giocatore corrente (1 o -1)
        """
        if board is None:
            self.board: List[List[int | None]] = [
                [None for _ in range(3)] for _ in range(3)
            ]
        else:
            # Copia profonda per evitare aliasing
            self.board = [row[:] for row in board]

        self.current_player: int = current_player
        self._legal_moves_cache: List[Tuple[int, int]] | None = None
        self._cache_valid: bool = False

    def __repr__(self) -> str:
        """Rappresentazione stringata dello stato per debugging."""
        lines: List[str] = ["TicTacToeState:"]
        for row in self.board:
            row_str = "  "
            for cell in row:
                if cell is None:
                    row_str += ". "
                elif cell == 1:
                    row_str += "X "
                else:  # -1
                    row_str += "O "
            lines.append(row_str)
        lines.append(f"  Current player: {self.current_player}")
        winner = self.get_winner()
        if winner is not None:
            lines.append(f"  Winner: {winner}")
        return "\n".join(lines)

    def get_legal_moves(self) -> List[Tuple[int, int]]:
        """
        Restituisce la lista delle mosse legali (celle vuote).
        Utilizza cache per evitare ricalcoli.

        Returns:
            Lista delle coordinate delle celle vuote
        """
        if self._cache_valid:
            return self._legal_moves_cache if self._legal_moves_cache is not None else []

        moves: List[Tuple[int, int]] = []
        for i in range(3):
            for j in range(3):
                if self.board[i][j] is None:
                    moves.append((i, j))

        self._legal_moves_cache = moves
        self._cache_valid = True
        return moves

    def make_move(self, move: Tuple[int, int]) -> TicTacToeState:
        """
        Esegue una mossa e restituisce il nuovo stato (immutabilità: lo
        stato corrente non viene modificato).

        Args:
            move: Tupla (riga, colonna) della mossa

        Returns:
            Nuovo stato di TicTacToe dopo la mossa
        """
        row_idx, col_idx = move
        new_board = [row[:] for row in self.board]
        new_board[row_idx][col_idx] = self.current_player
        return TicTacToeState(new_board, -self.current_player)

    def is_terminal(self) -> bool:
        """
        Verifica se lo stato è terminale (partita finita).

        Returns:
            True se c'è un vincitore o il tabellone è pieno
        """
        return self.get_winner() is not None or len(self.get_legal_moves()) == 0

    def get_result(self, player: int) -> GameResult:
        """
        Restituisce il risultato della partita dal punto di vista del giocatore.

        Args:
            player: ID del giocatore

        Returns:
            WIN, LOSS, DRAW, o ONGOING
        """
        winner = self.get_winner()
        if winner is None:
            if len(self.get_legal_moves()) == 0:
                return GameResult.DRAW
            else:
                return GameResult.ONGOING
        elif winner == player:
            return GameResult.WIN
        else:
            return GameResult.LOSS

    def get_current_player(self) -> int:
        """Restituisce l'ID del giocatore corrente."""
        return self.current_player

    def key(self) -> Tuple[Any, ...]:
        """Chiave hashable per la tabella di trasposizione del minimax."""
        return (tuple(tuple(row) for row in self.board), self.current_player)

    def get_winner(self) -> int | None:
        """
        Determina se c'è un vincitore.

        Returns:
            ID del vincitore (1 o -1), o None se non c'è vincitore
        """
        # Controlla righe
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]

        # Controlla colonne
        for col in range(3):
            if (self.board[0][col] == self.board[1][col] == self.board[2][col]
                    and self.board[0][col] is not None):
                return self.board[0][col]

        # Controlla diagonale principale
        if (self.board[0][0] == self.board[1][1] == self.board[2][2]
                and self.board[0][0] is not None):
            return self.board[0][0]

        # Controlla diagonale secondaria
        if (self.board[0][2] == self.board[1][1] == self.board[2][0]
                and self.board[0][2] is not None):
            return self.board[0][2]

        return None

    def evaluate_position(self, player: int) -> float:
        """
        Valuta la qualità della posizione per un giocatore dato.
        Favorisce il controllo del centro e degli angoli.

        Args:
            player: ID del giocatore

        Returns:
            Score posizionale (più alto è migliore per il giocatore)
        """
        winner = self.get_winner()
        if winner == player:
            return 100.0
        elif winner == -player:
            return -100.0

        score: float = 0.0

        # Valuta tutte le righe e colonne
        lines: List[List[int | None]] = []
        for i in range(3):
            lines.append([self.board[i][j] for j in range(3)])
            lines.append([self.board[j][i] for j in range(3)])

        # Valuta le diagonali
        lines.append([self.board[i][i] for i in range(3)])
        lines.append([self.board[i][2 - i] for i in range(3)])

        for line in lines:
            score += self._evaluate_line(line, player)

        # Bonus per il controllo del centro
        if self.board[1][1] == player:
            score += 3

        # Bonus per il controllo degli angoli
        corners: List[Tuple[int, int]] = [(0, 0), (0, 2), (2, 0), (2, 2)]
        for r, c in corners:
            if self.board[r][c] == player:
                score += 2

        return score

    def _evaluate_line(self, line: List[int | None], player: int) -> float:
        """
        Valuta una linea (riga, colonna o diagonale).

        Args:
            line: Lista di tre celle
            player: ID del giocatore

        Returns:
            Score della linea
        """
        player_count: int = line.count(player)
        opponent_count: int = line.count(-player)
        empty_count: int = line.count(None)

        # Se la linea è "contaminata" (ha sia player che opponent), vale 0
        if opponent_count > 0 and player_count > 0:
            return 0

        # Se il player ha 2 celle e una è vuota, è una minaccia (score alto)
        if player_count == 2 and empty_count == 1:
            return 5

        # Se il player ha 1 cella e due sono vuote, potenziale futuro
        if player_count == 1 and empty_count == 2:
            return 1

        # Se l'opponent ha 2 celle e una è vuota, è una minaccia (score negativo)
        if opponent_count == 2 and empty_count == 1:
            return -5

        # Se l'opponent ha 1 cella e due sono vuote, futuro negativo
        if opponent_count == 1 and empty_count == 2:
            return -1

        return 0
