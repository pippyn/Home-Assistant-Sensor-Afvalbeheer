# API Restructure Plan

## Current State Analysis

The current `API.py` file is 1,617 lines containing:
- 4 core classes: `WasteCollectionRepository`, `WasteCollection`, `WasteData`, `WasteCollector` (abstract base)
- 16 distinct collector implementations
- Collector selection logic in `WasteData.__select_collector()` (lines 144-178)

### Collector Categories Identified

1. **Ximmio-based collectors** (20+ municipalities)
   - Single `XimmioCollector` class serving multiple collectors via configuration
   - Uses `XIMMIO_COLLECTOR_IDS` mapping from `const.py`

2. **Burgerportaal-based collectors** (10+ municipalities)  
   - Single `BurgerportaalCollector` class
   - Uses `BURGERPORTAAL_COLLECTOR_IDS` mapping

3. **Opzet-based collectors** (5+ municipalities)
   - Single `OpzetCollector` class  
   - Uses `OPZET_COLLECTOR_URLS` mapping

4. **Individual API collectors** (11 unique implementations)
   - AfvalAlert, Afvalwijzer, Circulus, Cleanprofs, DeAfvalApp
   - LimburgNet, MontferlandNet, Omrin, RD4, ROVA, RecycleApp, Straatbeeld

## Proposed New Structure

### Directory Structure
```
custom_components/afvalbeheer/
├── collectors/
│   ├── __init__.py
│   ├── base.py                    # WasteCollector base class
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── ximmio.py             # XimmioCollector
│   │   ├── burgerportaal.py      # BurgerportaalCollector  
│   │   └── opzet.py              # OpzetCollector
│   └── individual/
│       ├── __init__.py
│       ├── afval_alert.py        # AfvalAlertCollector
│       ├── afvalwijzer.py        # AfvalwijzerCollector
│       ├── circulus.py           # CirculusCollector
│       ├── cleanprofs.py         # CleanprofsCollector
│       ├── deafvalapp.py         # DeAfvalAppCollector
│       ├── limburg_net.py        # LimburgNetCollector
│       ├── montferland_net.py    # MontferlandNetCollector
│       ├── omrin.py              # OmrinCollector
│       ├── rd4.py                # RD4Collector
│       ├── rova.py               # ROVACollector
│       ├── recycle_app.py        # RecycleApp
│       └── straatbeeld.py        # StraatbeeldCollector
├── models/
│   ├── __init__.py
│   ├── waste_collection.py       # WasteCollection class
│   └── waste_repository.py       # WasteCollectionRepository class
├── API.py                        # Slimmed down - WasteData + collector factory
└── ... (other existing files)
```

### Key Design Principles

1. **Separation of Concerns**
   - Models in dedicated `models/` package
   - Collectors grouped by API pattern
   - Clear inheritance hierarchy

2. **Maintainability**
   - Each collector in its own file (≤100 lines each)
   - Shared functionality in base classes
   - Easy to add new collectors

3. **Backward Compatibility**
   - Existing imports continue to work
   - No changes to public API
   - Gradual migration possible

4. **Simplicity**
   - Logical grouping (shared vs individual)
   - Consistent naming conventions
   - Clear module boundaries

## Implementation Strategy

### Phase 1: Extract Models (Low Risk)
- Move `WasteCollection` → `models/waste_collection.py`
- Move `WasteCollectionRepository` → `models/waste_repository.py`
- Update imports in `API.py`

### Phase 2: Extract Base Class (Low Risk)
- Move `WasteCollector` → `collectors/base.py`
- Update imports in `API.py`

### Phase 3: Extract Shared Collectors (Medium Risk)
- Move `XimmioCollector` → `collectors/shared/ximmio.py`
- Move `BurgerportaalCollector` → `collectors/shared/burgerportaal.py`
- Move `OpzetCollector` → `collectors/shared/opzet.py`
- Update collector mapping in `WasteData.__select_collector()`

### Phase 4: Extract Individual Collectors (Medium Risk)
- Move remaining 11 collectors to `collectors/individual/`
- One collector per file
- Update collector mapping

### Phase 5: Cleanup (Low Risk)
- Remove extracted classes from `API.py`
- Add proper `__init__.py` files with exports
- Update documentation

## Benefits

### For Developers
- **Easier Navigation**: Find specific collector logic quickly
- **Reduced Merge Conflicts**: Changes isolated to specific files
- **Better Testing**: Test individual collectors independently
- **Clear Dependencies**: Understand what each collector needs

### for Maintenance
- **Faster Debugging**: Smaller files easier to understand
- **Simpler Updates**: Modify one collector without affecting others
- **Better Code Review**: Focused changes in specific files
- **Documentation**: Each collector can have dedicated docs

### For New Contributors
- **Lower Barrier**: Understand one collector at a time
- **Clear Examples**: See patterns in shared vs individual collectors
- **Easy Addition**: Add new collector by copying similar pattern

## Risk Mitigation

1. **Import Compatibility**: Maintain existing imports via `__init__.py` exports
2. **Gradual Migration**: Implement phase by phase with testing
3. **Rollback Plan**: Each phase can be reverted independently
4. **Testing Strategy**: Test each collector after extraction

## File Size Estimates

After restructuring:
- `API.py`: ~200 lines (WasteData + factory + utilities)
- Individual collector files: 50-150 lines each
- Shared collector files: 100-200 lines each
- Model files: 50-100 lines each

This reduces the largest file from 1,617 lines to manageable chunks while maintaining all functionality.