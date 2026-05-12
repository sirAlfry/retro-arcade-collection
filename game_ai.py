# game_ai.py
# Migliorato: robustezza, timeout controllato, protezione sugli stati esterni,
# memoria efficiente, e strategie di ricerca avanzate
import random
import copy
import time
from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional, Dict, Set
from enum import Enum


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

    @abstractmethod
    def get_legal_moves(self) -> List[Any]:
        """Restituisce la lista delle mosse legali disponibili."""
        pass

    @abstractmethod
    def make_move(self, move: Any) -> 'GameState':
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

    def copy(self) -> 'GameState':
        """Crea una copia profonda dello stato di gioco."""
        return copy.deepcopy(self)


class GameAI:
    """
    Motore AI per giochi con supporto per minimax, alpha-beta pruning,
    deepening iterativo, euristica e mosse casuali.
    """

    __slots__ = (
        'algorithm', 'difficulty', 'time_limit', 'player_id',
        'nodes_evaluated', 'start_time', '_best_move_by_depth'
    )

    def __init__(
        self,
        algorithm: str = "minimax",
        difficulty: int = 3,
        time_limit: float = 5.0,
        player_id: int = -1
    ) -> None:
        """
        Inizializza l'AI del gioco.

        Args:
            algorithm: Algoritmo da utilizzare ('minimax', 'alpha_beta', 'random', 'heuristic')
            difficulty: Profondità di ricerca (1-6)
            time_limit: Tempo massimo per trovare una mossa in secondi
            player_id: ID del giocatore AI
        """
        if isinstance(algorithm, AIAlgorithm):
            self.algorithm: AIAlgorithm = algorithm
        else:
            alg_str = str(algorithm).lower()
            found: Optional[AIAlgorithm] = None
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

        self.difficulty: int = max(1, min(6, difficulty))
        self.time_limit: float = max(0.01, float(time_limit))
        self.player_id: int = player_id
        self.nodes_evaluated: int = 0
        self.start_time: float = 0.0
        self._best_move_by_depth: Optional[Any] = None

    def get_best_move(self, state: GameState) -> Optional[Any]:
        """
        Calcola la miglior mossa per lo stato di gioco dato.

        Args:
            state: Lo stato corrente del gioco

        Returns:
            La miglior mossa trovata, o None se non disponibile
        """
        try:
            legal_moves = state.get_legal_moves()
        except Exception:
            return None

        if not legal_moves:
            return None

        self.nodes_evaluated = 0
        self.start_time = time.time()
        self._best_move_by_depth = None

        try:
            if self.algorithm == AIAlgorithm.RANDOM:
                return self._random_move(legal_moves)
            elif self.algorithm == AIAlgorithm.MINIMAX:
                return self._minimax_move(state, legal_moves)
            elif self.algorithm == AIAlgorithm.ALPHA_BETA:
                return self._alpha_beta_move(state, legal_moves)
            elif self.algorithm == AIAlgorithm.HEURISTIC:
                return self._heuristic_move(state, legal_moves)
            return random.choice(legal_moves)
        except Exception:
            # fallback robusto
            try:
                return random.choice(legal_moves)
            except Exception:
                return None

    def _random_move(self, legal_moves: List[Any]) -> Any:
        """Seleziona una mossa casuale."""
        return random.choice(legal_moves)

    def _minimax_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando minimax con deepening iterativo.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        best_move: Optional[Any] = None
        max_depth = max(1, self.difficulty)

        # Deepening iterativo: prova profondità 1, 2, 3... fino a max_depth
        for current_depth in range(1, max_depth + 1):
            if self._is_time_up():
                break

            depth_best_move: Optional[Any] = None
            depth_best_value: float = float('-inf')

            for move in legal_moves:
                if self._is_time_up():
                    break
                try:
                    new_state = state.make_move(move)
                    value = self._minimax(new_state, current_depth - 1, False)
                    if value > depth_best_value:
                        depth_best_value = value
                        depth_best_move = move
                except Exception:
                    continue

            if depth_best_move is not None:
                best_move = depth_best_move

        return best_move if best_move is not None else random.choice(legal_moves)

    def _alpha_beta_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando alpha-beta pruning con deepening iterativo.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        best_move: Optional[Any] = None
        max_depth = max(1, self.difficulty)

        # Deepening iterativo con ordinamento delle mosse
        for current_depth in range(1, max_depth + 1):
            if self._is_time_up():
                break

            # Ordina le mosse per migliorare il pruning
            ordered_moves = self._order_moves(state, legal_moves)

            depth_best_move: Optional[Any] = None
            depth_best_value: float = float('-inf')
            alpha: float = float('-inf')
            beta: float = float('inf')

            for move in ordered_moves:
                if self._is_time_up():
                    break
                try:
                    new_state = state.make_move(move)
                    value = self._alpha_beta(new_state, current_depth - 1, alpha, beta, False)
                    if value > depth_best_value:
                        depth_best_value = value
                        depth_best_move = move
                    alpha = max(alpha, value)
                except Exception:
                    continue

            if depth_best_move is not None:
                best_move = depth_best_move

        return best_move if best_move is not None else random.choice(legal_moves)

    def _heuristic_move(self, state: GameState, legal_moves: List[Any]) -> Any:
        """
        Calcola la miglior mossa usando un'euristica di valutazione diretta.

        Args:
            state: Lo stato corrente del gioco
            legal_moves: Lista delle mosse legali disponibili

        Returns:
            La miglior mossa trovata
        """
        best_move: Optional[Any] = None
        best_value: float = float('-inf')

        for move in legal_moves:
            try:
                new_state = state.make_move(move)
                value = new_state.evaluate_position(self.player_id)
                if value > best_value:
                    best_value = value
                    best_move = move
            except Exception:
                continue

        return best_move if best_move is not None else random.choice(legal_moves)

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
            depth: Profondità attuale per favorire vittorie rapide

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
        Algoritmo minimax ricorsivo.

        Args:
            state: Lo stato corrente del gioco
            depth: Profondità rimanente di ricerca
            maximizing: True se è il turno del massimizzatore

        Returns:
            Il valore minimax dello stato
        """
        self.nodes_evaluated += 1

        if depth == 0 or state.is_terminal() or self._is_time_up():
            return self._evaluate_terminal(state, depth)

        if maximizing:
            max_value: float = float('-inf')
            for move in state.get_legal_moves():
                try:
                    new_state = state.make_move(move)
                    value = self._minimax(new_state, depth - 1, False)
                    max_value = max(max_value, value)
                    if self._is_time_up():
                        break
                except Exception:
                    continue
            return max_value
        else:
            min_value: float = float('inf')
            for move in state.get_legal_moves():
                try:
                    new_state = state.make_move(move)
                    value = self._minimax(new_state, depth - 1, True)
                    min_value = min(min_value, value)
                    if self._is_time_up():
                        break
                except Exception:
                    continue
            return min_value

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

        if depth == 0 or state.is_terminal() or self._is_time_up():
            return self._evaluate_terminal(state, depth)

        if maximizing:
            max_value: float = float('-inf')
            for move in state.get_legal_moves():
                try:
                    new_state = state.make_move(move)
                    value = self._alpha_beta(new_state, depth - 1, alpha, beta, False)
                    max_value = max(max_value, value)
                    alpha = max(alpha, value)
                    if beta <= alpha or self._is_time_up():
                        break
                except Exception:
                    continue
            return max_value
        else:
            min_value: float = float('inf')
            for move in state.get_legal_moves():
                try:
                    new_state = state.make_move(move)
                    value = self._alpha_beta(new_state, depth - 1, alpha, beta, True)
                    min_value = min(min_value, value)
                    beta = min(beta, value)
                    if beta <= alpha or self._is_time_up():
                        break
                except Exception:
                    continue
            return min_value

    def _is_time_up(self) -> bool:
        """Verifica se il tempo massimo è stato superato."""
        return time.time() - self.start_time > self.time_limit

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
            "time_taken": time.time() - self.start_time
        }


class TicTacToeState(GameState):
    """
    Implementazione dello stato di gioco per TicTacToe.
    Supporta valutazione posizionale, cache delle mosse legali.
    """

    __slots__ = ('board', 'current_player', '_legal_moves_cache', '_cache_valid')

    def __init__(
        self,
        board: Optional[List[List[Optional[int]]]] = None,
        current_player: int = 1
    ) -> None:
        """
        Inizializza lo stato di TicTacToe.

        Args:
            board: Matrice 3x3 rappresentante la scacchiera (None per vuota)
            current_player: ID del giocatore corrente (1 o -1)
        """
        if board is None:
            self.board: List[List[Optional[int]]] = [
                [None for _ in range(3)] for _ in range(3)
            ]
        else:
            # Copia profonda per evitare aliasing
            self.board = [row[:] for row in board]

        self.current_player: int = current_player
        self._legal_moves_cache: Optional[List[Tuple[int, int]]] = None
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

    def make_move(self, move: Tuple[int, int]) -> 'TicTacToeState':
        """
        Esegue una mossa e restituisce il nuovo stato.
        NOTA: Corregge il bug di shadowing della variabile 'row'.

        Args:
            move: Tupla (riga, colonna) della mossa

        Returns:
            Nuovo stato di TicTacToe dopo la mossa
        """
        row_idx, col_idx = move
        # CORRETTO: usa nomi di variabili diversi per evitare shadowing
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

    def get_winner(self) -> Optional[int]:
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
        lines: List[List[Optional[int]]] = []
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

    def _evaluate_line(self, line: List[Optional[int]], player: int) -> float:
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
