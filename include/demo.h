#pragma once


/**
 * A function in the global namespace.
 * 
 * This function will appear on the index page.
 */
void scopeless();


/**
 * An example namespace.
 */
namespace demo {

/**
 * A simple class.
 */
class parent {
    public:
        /**
         * Frobnicates baz.
         * @param baz Baz.
         * @return An integer.
         */
        int foo(int baz);
        
        /**
         * Returns nothing.
         * @return Something.
         */
        double bar();
};

/**
 * A TMP factorial implementation - generic version
 * @tparam n The value.
 */
template<int n>
struct factorial {
    enum { 
        /** 
         * The factorial of n
         */
        value = n * factorial<n-1>::value 
    };
};

/**
 * A template specialization for "0!"
 */
template<>
struct factorial<0> {
    enum { 
        /** 
         * The factorial of 0
         */
        value = 1; 
    }
};


} // namespace demo
