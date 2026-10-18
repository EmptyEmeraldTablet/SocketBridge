// TSTL plugin: compile-time inline enum/flag values from isaac-typescript-definitions.
//
// The definitions package exports hundreds of regular TypeScript enums. By default TSTL emits each
// enum as a Lua table, and importing the barrel pulls every table into the bundle. This plugin
// turns member accesses into numeric/string literals, then elides the corresponding Lua require when
// (and only when) every value-position reference of the imported names is such a member access.
// TypeScript still sees the package for type checking and for the global Isaac/Lua declarations.
//
// Since DEVELOPMENT_RECOMMENDATIONS.md §4.1: when an import *cannot* be fully elided, we print a
// visible warning (once per file + retained name) instead of silently keeping the runtime require,
// so a beginner can immediately see why the bundle suddenly grew.
const ts = require("typescript");
const tstl = require("typescript-to-lua");

const DEFINITIONS_MARKER = "isaac-typescript-definitions";

// Warn once per (file, retained-name, reason) so busy files do not spam the console.
const warnedKeys = new Set();

function isDefinitionsFile(fileName) {
  return fileName.includes(DEFINITIONS_MARKER);
}

function isDefinitionsModuleSpecifier(specifier) {
  return (
    specifier === "isaac-typescript-definitions" ||
    specifier.startsWith("isaac-typescript-definitions/")
  );
}

function numericOrStringLiteral(value, originalNode) {
  if (typeof value === "number") return tstl.createNumericLiteral(value, originalNode);
  if (typeof value === "string") return tstl.createStringLiteral(value, originalNode);
  return undefined;
}

function enumMemberConstantFromSymbol(context, symbol) {
  const declaration = symbol?.valueDeclaration;
  if (!declaration || !ts.isEnumMember(declaration)) return undefined;
  if (!isDefinitionsFile(declaration.getSourceFile().fileName)) return undefined;
  return context.checker.getConstantValue(declaration);
}

function literalForPropertyAccess(context, node) {
  // Built-in const-enum path.
  const directValue = context.checker.getConstantValue(node);
  const directLiteral = numericOrStringLiteral(directValue, node);
  if (directLiteral) return directLiteral;

  // Regular enum: `EntityType.FAMILIAR`.
  const symbol = context.checker.getSymbolAtLocation(node.name);
  if (symbol && (symbol.flags & ts.SymbolFlags.EnumMember) !== 0) {
    const value = enumMemberConstantFromSymbol(context, symbol);
    if (value !== undefined) return numericOrStringLiteral(value, node);
  }

  // The bit-flag objects are not real TS enums, so leave them to the normal
  // table lookup (or use `import type` + local constants in your code).
  return undefined;
}

function literalForElementAccess(context, node) {
  const directValue = context.checker.getConstantValue(node);
  const directLiteral = numericOrStringLiteral(directValue, node);
  if (directLiteral) return directLiteral;

  if (ts.isStringLiteralLike(node.argumentExpression)) {
    const enumType = context.checker.getTypeAtLocation(node.expression);
    const property = context.checker.getPropertyOfType(enumType, node.argumentExpression.text);
    if (property) {
      const value = enumMemberConstantFromSymbol(context, property);
      if (value !== undefined) return numericOrStringLiteral(value, node);
    }
  }
  return undefined;
}

function isTypePosition(node) {
  let parent = node.parent;
  while (parent) {
    if (ts.isTypeNode(parent)) return true;
    // Stop when we reach an expression/statement/declaration; type positions are above them.
    if (
      ts.isExpression(parent) ||
      ts.isStatement(parent) ||
      ts.isDeclaration(parent) ||
      ts.isSourceFile(parent)
    ) {
      return false;
    }
    parent = parent.parent;
  }
  return false;
}

// Whether a member-access usage resolves to an inlinable literal.
function literalForReferenceParent(context, parent) {
  if (ts.isPropertyAccessExpression(parent)) {
    return literalForPropertyAccess(context, parent);
  }
  if (ts.isElementAccessExpression(parent)) {
    return literalForElementAccess(context, parent);
  }
  return undefined;
}

/**
 * Analyze one definitions import declaration.
 *
 * Returns:
 * - `elidable`: true => every value use was inlined, the runtime require can be dropped.
 * - `suppressWarn`: true => the file already has broken references (TS will error anyway);
 *   do not warn.
 * - `reasons`: [{ name, reason }] for names that keep the require alive.
 */
function analyzeDefinitionsImport(context, importDeclaration) {
  const sourceFile = context.sourceFile;
  const importClause = importDeclaration.importClause;

  // Side-effect-only import (`import "isaac-typescript-definitions"`).
  if (!importClause) {
    return { elidable: false, suppressWarn: false, reasons: [{ name: "<side-effect import>", reason: "整包副作用导入" }] };
  }

  // Namespace import (`import * as Defs from ...`).
  if (!ts.isNamedImports(importClause.namedBindings)) {
    return { elidable: false, suppressWarn: false, reasons: [{ name: importClause.name?.text ?? "*", reason: "命名空间导入（改用具名 import，让插件可逐名内联/删掉）" }] };
  }

  const identifiersBySymbol = new Map();
  const collectIdentifiers = (node) => {
    if (ts.isIdentifier(node)) {
      const symbol = context.checker.getSymbolAtLocation(node);
      if (symbol) {
        const bucket = identifiersBySymbol.get(symbol);
        if (bucket) bucket.push(node);
        else identifiersBySymbol.set(symbol, [node]);
      }
    }
    ts.forEachChild(node, collectIdentifiers);
  };
  collectIdentifiers(sourceFile);

  const reasons = [];
  for (const importSpecifier of importClause.namedBindings.elements) {
    const localSymbol = context.checker.getSymbolAtLocation(importSpecifier.name);
    if (!localSymbol) {
      // Unknown import -> TS will already report it; keep the require, stay silent.
      return { elidable: false, suppressWarn: true, reasons: [] };
    }
    const references = identifiersBySymbol.get(localSymbol) ?? [];
    let unresolvedMember = false;
    const keptValueRefs = [];
    for (const identifier of references) {
      if (identifier === importSpecifier.name) continue;
      if (isTypePosition(identifier)) continue;
      if (literalForReferenceParent(context, identifier.parent) !== undefined) continue;

      // Value-position use that cannot be inlined; classify for the warning message.
      if (ts.isPropertyAccessExpression(identifier.parent) && identifier.parent.expression === identifier) {
        const memberSymbol = context.checker.getSymbolAtLocation(identifier.parent.name);
        if (!memberSymbol) {
          // Missing member (e.g. EntityType.DOES_NOT_EXIST) -> TS error coming, stay quiet.
          unresolvedMember = true;
          break;
        }
        keptValueRefs.push({
          kind: "member",
          name: importSpecifier.name.text,
          hint: "成员不是 enum（位标志/const 对象如 EntityFlag/ItemConfigTag 不能内联）",
        });
      } else if (ts.isElementAccessExpression(identifier.parent) && identifier.parent.expression === identifier) {
        keptValueRefs.push({
          kind: "element",
          name: importSpecifier.name.text,
          hint: "动态成员访问无法内联",
        });
      } else {
        keptValueRefs.push({
          kind: "bare",
          name: importSpecifier.name.text,
          hint: "把整个 enum 对象当值使用/传递（改为成员访问 EntityType.XXX 才能内联）",
        });
      }
    }
    if (unresolvedMember) {
      return { elidable: false, suppressWarn: true, reasons: [] };
    }
    reasons.push(...keptValueRefs);
  }

  return { elidable: reasons.length === 0, suppressWarn: false, reasons };
}

function warnOnce(importDeclaration, info) {
  const fileName = importDeclaration.getSourceFile().fileName;
  const signature = info.reasons.map((r) => `${r.name}|${r.reason}`).join(";");
  const key = `${fileName}|${signature}`;
  if (warnedKeys.has(key)) return;
  warnedKeys.add(key);

  const fileLabel = fileName.replace(/\\/g, "/");
  const detail = info.reasons.map((r) => `${r.name}（${r.reason}）`).join("、");
  console.warn(
    `[inlineIsaacEnums] ${fileLabel}: definitions import 无法完全内联，产物将保留运行时 require（会把整包 definitions 拉进 bundle）: ${detail}`,
  );
  console.warn(
    "  -> 优先写成成员访问（EntityType.XXX）；位标志对象请用 `import type` + 本地常量，见 OPTIMIZATION_GUIDE.md §4.2。",
  );
}

const plugin = {
  visitors: {
    [ts.SyntaxKind.PropertyAccessExpression]: (node, context) => {
      const literal = literalForPropertyAccess(context, node);
      if (literal) return literal;
      return context.superTransformExpression(node);
    },
    [ts.SyntaxKind.ElementAccessExpression]: (node, context) => {
      const literal = literalForElementAccess(context, node);
      if (literal) return literal;
      return context.superTransformExpression(node);
    },
    [ts.SyntaxKind.ImportDeclaration]: (node, context) => {
      if (
        ts.isStringLiteral(node.moduleSpecifier) &&
        isDefinitionsModuleSpecifier(node.moduleSpecifier.text)
      ) {
        // Only drop the runtime require when every value use was inlined above.
        const info = analyzeDefinitionsImport(context, node);
        if (info.elidable) return [];
        if (!info.suppressWarn) warnOnce(node, info);
        // Otherwise keep the require (the normal transform decides how to emit it).
      }
      return context.superTransformStatements(node);
    },
  },
};
module.exports = plugin;
