package com.java_counter.java_counter;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;

import java.io.IOException;
import java.nio.file.Paths;

public class Main {
    static int count = 0;

    public static void main(String[] args) throws java.io.IOException {
        StaticJavaParser.getConfiguration().setAttributeComments(false);
        CompilationUnit cu = StaticJavaParser.parse(Paths.get(args[0]));
        cu.accept(new VoidVisitorAdapter<Void>() {
            @Override
            public void visit(LambdaExpr n, Void arg) {
                count += 1;
            }
        }, null);
        System.out.print(count);
    }
}
